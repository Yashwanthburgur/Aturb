"""The assembly history, edit and rollback endpoints of the viewer client.

The module holds the safe reading of the two mutating request bodies and the
server-side service that edits an assembly and rolls a revision back. The
service calls the bounded assembly edit of the core, so the viewer never
reimplements the edit path. The configuration, the pack, the runner and the
model client are resolved when a request arrives, never when the viewer
starts. Every answer is sanitized: the paths of the host are stripped and the
credential of the environment is redacted.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from email.message import Message
from io import BufferedIOBase
from pathlib import Path

from aturb.agent.config import agent_settings, read_api_key
from aturb.agent.model import HttpModelClient
from aturb.agent.types import ModelClient
from aturb.assembly.manifest import AssemblyError, AssemblySpec, load_assembly
from aturb.assembly.revisions import (
    assembly_out_dir,
    load_assembly_history,
    rollback_assembly,
)
from aturb.config import active_pack, load_config, timeout_s
from aturb.contract.runner import Runner
from aturb.packs import default_packs_root, discover, load_runner
from clients.viewer.assembly_api import (
    AssemblyWorkspaceError,
    read_assembly_manifest,
)
from clients.viewer.generate_api import validate_local_request
from clients.viewer.http_utils import (
    MAX_BODY_BYTES as MAX_BODY_BYTES,
)
from clients.viewer.http_utils import (
    ApiError,
    SafeModelClient,
    configured_secrets,
    read_json_object,
    sanitize_message,
)

PROMPT_FILE_NAME = "agent.md"
NO_EDIT_HANDLER = "assembly editing is not available"
NO_ROLLBACK_HANDLER = "assembly rollback is not available"
NO_ASSEMBLY_SERVICE = "the assembly service is not available"
BUSY_MESSAGE = "another edit is already running"
NOT_AN_ASSEMBLY = "the workspace holds no assembly"
ROLLBACK_REFUSED = "the revision cannot be selected"


def read_assembly_instruction(headers: Message[str, str], rfile: BufferedIOBase,
                              bound_port: int, handler: object | None) -> str:
    """Read the instruction of one assembly edit request, or refuse it."""
    return _read_field(headers, rfile, bound_port, handler, "instruction",
                       NO_EDIT_HANDLER)


def read_assembly_revision(headers: Message[str, str], rfile: BufferedIOBase,
                           bound_port: int, handler: object | None) -> str:
    """Read the revision id of one assembly rollback request, or refuse it."""
    return _read_field(headers, rfile, bound_port, handler, "revision_id",
                       NO_ROLLBACK_HANDLER)


def read_assembly_history_payload(service: "AssemblyEditService | None") -> dict:
    """Return the revision history of the assembly, or refuse the request."""
    if service is None:
        raise ApiError(503, NO_ASSEMBLY_SERVICE)
    return service.history()


class AssemblyEditService:
    """The server-side assembly edit and rollback service of the viewer.

    The seams are resolved when a request arrives, never when the viewer
    starts. One edit runs at a time and the lock is the one of the other
    services, so a generation, an edit and a rollback never race.
    """

    def __init__(self, workspace_dir: Path, config_path: Path | None = None,
                 lock: threading.Lock | None = None,
                 client_factory: Callable[[dict, str],
                                          ModelClient] | None = None,
                 runner_factory: Callable[[
                     str, dict, Path], Runner] | None = None,
                 ) -> None:
        """Take the workspace, the configuration and the seams the tests replace."""
        self._workspace_dir = Path(workspace_dir)
        self._config_path = Path(config_path) if config_path else None
        self._lock = lock if lock is not None else threading.Lock()
        self._client_factory = client_factory or HttpModelClient.from_settings
        self._runner_factory = runner_factory or load_runner

    def history(self) -> dict:
        """Return the revision history of the assembly as a JSON-ready payload."""
        root, _, spec = self._assembly()
        history = load_assembly_history(
            assembly_out_dir(root, spec.assembly_id))
        revisions = [] if history is None else list(
            history.get("revisions", []))
        active = "" if history is None else str(
            history.get("active_revision", ""))
        return {"assembly_id": spec.assembly_id, "has_history": history is not None,
                "active_revision": active, "editable": True,
                "revisions": [_revision(entry) for entry in revisions]}

    def edit(self, instruction: str) -> dict:
        """Edit the parts of the assembly and return the outcome."""
        if not isinstance(instruction, str) or not instruction.strip():
            raise ApiError(400, "the instruction is empty")
        root, path, spec = self._assembly()
        if not self._lock.acquire(blocking=False):
            raise ApiError(409, BUSY_MESSAGE)
        try:
            return self._edit(root, path, spec, instruction.strip())
        finally:
            self._lock.release()

    def rollback(self, revision_id: str) -> dict:
        """Restore a verified revision of the assembly and return the history."""
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ApiError(400, "the revision id is empty")
        root, path, _ = self._assembly()
        if not self._lock.acquire(blocking=False):
            raise ApiError(409, BUSY_MESSAGE)
        try:
            rollback_assembly(root, path, revision_id.strip())
        except AssemblyError:
            raise ApiError(400, ROLLBACK_REFUSED) from None
        except Exception:
            raise ApiError(422, ROLLBACK_REFUSED) from None
        finally:
            self._lock.release()
        return self.history()

    def _assembly(self) -> tuple[Path, Path, AssemblySpec]:
        """Return the project, the manifest and the spec of the assembly."""
        try:
            result = read_assembly_manifest(self._workspace_dir)
            assembly_file = str(result.get("assembly_file", ""))
            root = _project_root(self._workspace_dir, assembly_file)
            if root is None:
                raise ApiError(400, NOT_AN_ASSEMBLY)
            path = root / assembly_file
            spec = load_assembly(path)
        except (AssemblyWorkspaceError, AssemblyError):
            raise ApiError(400, NOT_AN_ASSEMBLY) from None
        return root, path, spec

    def _edit(self, root: Path, path: Path, spec: AssemblySpec,
              instruction: str) -> dict:
        """Resolve the seams and run the bounded assembly edit of the core."""
        from aturb.assembly.agent import edit_assembly

        settings: dict | None = None
        try:
            cfg = load_config(self._config_path)
            settings = agent_settings(cfg)
            name = active_pack(cfg)
            packs_root = default_packs_root()
            manifests = discover(packs_root)
            if name not in manifests:
                raise ApiError(422, "the active pack is not installed")
            runner = self._runner_factory(name, cfg, packs_root)
            api_key = read_api_key(settings)
            client = self._client_factory(settings, api_key)
            client = SafeModelClient(
                client, configured_secrets(settings) + (api_key,))
            pack = manifests[name]
            prompt = (pack.pack_dir / pack.prompt_dir / PROMPT_FILE_NAME).read_text(
                encoding="utf-8")
            result = edit_assembly(
                root, path, instruction, client=client, runner=runner,
                settings=settings, pack_prompt=prompt,
                timeout_s=timeout_s(cfg), record_revision=True)
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(422, sanitize_message(str(exc), settings)) from None
        return {"assembly_id": result.assembly_id, "status": result.status,
                "stop_reason": result.stop_reason, "promoted": result.promoted,
                "attempts": result.attempts, "revision_id": result.revision_id,
                "parent_revision": result.parent_revision,
                "updated_parts": list(result.updated_parts),
                "error": sanitize_message(result.error, settings)}


def _read_field(headers: Message[str, str], rfile: BufferedIOBase,
                bound_port: int, handler: object | None, field: str,
                missing: str) -> str:
    """Read one text field of one request, or refuse the request.

    The order is fixed: the local host and origin, then the handler, then the
    length of the body, then the body itself, and only then the field. A
    refusal never reads the body.
    """
    reason = validate_local_request(
        headers.get("Host"), headers.get("Origin"), bound_port)
    if reason is not None:
        raise ApiError(403, reason)
    if handler is None:
        raise ApiError(503, missing)
    payload = read_json_object(headers, rfile)
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, f"the {field} is missing or empty")
    return value.strip()


def _project_root(workspace_dir: Path, assembly_file: str) -> Path | None:
    """Return the project that owns the assembly workspace, or None."""
    if not assembly_file:
        return None
    for parent in Path(workspace_dir).resolve().parents:
        if (parent / assembly_file).is_file():
            return parent
    return None


def _revision(entry: dict) -> dict:
    """Return one revision of a history as a JSON-ready payload."""
    return {"id": str(entry.get("id", "")), "parent": str(entry.get("parent", "")),
            "kind": str(entry.get("kind", "")), "status": str(entry.get("status", "")),
            "stop_reason": str(entry.get("stop_reason", "")),
            "instruction": str(entry.get("instruction", "")),
            "attempts": int(entry.get("attempts", 0)),
            "updated_parts": [str(part) for part in entry.get("updated_parts", [])]}
