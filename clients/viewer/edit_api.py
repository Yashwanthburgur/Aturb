"""The history, edit and rollback endpoints of the viewer client.

The module holds the serialization of a revision history, the safe reading of
the two mutating request bodies, and the server-side service that edits a
workspace and rolls a revision back. The service calls the expectation-free
edit of the core, so the viewer never reimplements the generation path. The
configuration, the pack, the runner and the model client are resolved when a
request arrives, never when the viewer starts, so a read-only viewer needs
neither a configuration nor a credential. Every answer is sanitized: the paths
of the host are stripped and the credential of the environment is redacted.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from email.message import Message
from io import BufferedIOBase
from pathlib import Path

from aturb.agent.config import agent_settings, read_api_key
from aturb.agent.edit import edit_part
from aturb.agent.model import HttpModelClient
from aturb.agent.revisions import (
    RevisionError,
    is_verified_manifest,
    load_history,
    rollback_revision,
)
from aturb.agent.types import ModelClient, ModelRequest, ModelResponse
from aturb.config import active_pack, load_config, timeout_s
from aturb.packs import default_packs_root, discover, load_runner
from clients.viewer.generate_api import (
    REDACTED,
    ApiError,
    _content_length,
    _safe,
    _secrets,
    validate_local_request,
)
from clients.viewer.workspace import LoadedWorkspace, load_workspace

HISTORY_FILE_NAME = "history.toml"
NO_EDIT_HANDLER = "editing is not available"
NO_ROLLBACK_HANDLER = "rollback is not available"
BUSY_MESSAGE = "another edit is already running"
ROLLBACK_REFUSED = "the revision cannot be selected"
UNANSWERED = "the request could not be answered"

EditHandler = Callable[[LoadedWorkspace, str],
                       tuple[LoadedWorkspace | None, dict]]
RollbackHandler = Callable[[LoadedWorkspace, str],
                           tuple[LoadedWorkspace, dict]]


@dataclass(frozen=True)
class EditOutcome:
    """What one edit or rollback produced: the status, the body and the workspace."""

    status: int
    payload: dict
    workspace: LoadedWorkspace | None = None


def read_edit_instruction(headers: Message[str, str], rfile: BufferedIOBase,
                          bound_port: int, handler: EditHandler | None) -> str:
    """Read the instruction of one edit request, or refuse the request."""
    return _read_field(headers, rfile, bound_port, handler, "instruction",
                       NO_EDIT_HANDLER)


def read_rollback_revision(headers: Message[str, str], rfile: BufferedIOBase,
                           bound_port: int, handler: RollbackHandler | None) -> str:
    """Read the revision id of one rollback request, or refuse the request."""
    return _read_field(headers, rfile, bound_port, handler, "revision_id",
                       NO_ROLLBACK_HANDLER)


def run_edit(handler: EditHandler | None, workspace: LoadedWorkspace,
             instruction: str) -> EditOutcome:
    """Run one edit and return what the endpoint answers.

    A busy service answers 409, a refused edit answers 422, a failure 500.
    """
    return _run(handler, workspace, instruction, NO_EDIT_HANDLER)


def run_rollback(handler: RollbackHandler | None, workspace: LoadedWorkspace,
                 revision_id: str) -> EditOutcome:
    """Run one rollback and return what the endpoint answers."""
    return _run(handler, workspace, revision_id, NO_ROLLBACK_HANDLER)


def read_history_payload(workspace: LoadedWorkspace) -> dict:
    """Return the revision history of a workspace as a JSON-ready payload.

    The payload names no path of the host, only the fields of the revisions.
    """
    root = Path(workspace.history_root or workspace.root)
    if (root / HISTORY_FILE_NAME).is_file():
        try:
            history = load_history(root)
        except RevisionError:
            return {"has_history": True, "active_revision": None,
                    "editable": False, "revisions": []}
        return {"has_history": True, "active_revision": history.active_revision,
                "editable": True, "revisions": [_revision(e) for e in history.revisions]}
    return {"has_history": False, "active_revision": None,
            "editable": is_verified_manifest(workspace.manifest),
            "revisions": []}


class EditService:
    """The server-side edit and rollback service of the viewer.

    The seams are resolved when a request arrives, never when the viewer
    starts. One edit runs at a time and the lock is the one of the generation
    service, so a generation, an edit and a rollback never race.
    """

    def __init__(self, *, config_loader: Callable[[], dict] = load_config,
                 packs_root: Path | None = None,
                 client_factory: Callable[[dict, str],
                                          ModelClient] | None = None,
                 lock: threading.Lock | None = None) -> None:
        """Take the seams the tests replace and the lock the services share."""
        self._config_loader = config_loader
        self._packs_root = (Path(packs_root) if packs_root is not None
                            else default_packs_root())
        self._client_factory = client_factory or _default_client_factory
        self._lock = lock if lock is not None else threading.Lock()

    def edit(self, workspace: LoadedWorkspace, instruction: str
             ) -> tuple[LoadedWorkspace | None, dict]:
        """Edit the active revision of a workspace and return the outcome.

        The workspace is reloaded after the edit, so the viewer follows the
        active revision: the new one when the edit verified, the last verified
        one when it did not.
        """
        if not isinstance(instruction, str) or not instruction.strip():
            raise ApiError(400, "the instruction is empty")
        if not self._lock.acquire(blocking=False):
            raise ApiError(409, BUSY_MESSAGE)
        try:
            return self._edit(workspace, instruction.strip())
        finally:
            self._lock.release()

    def rollback(self, workspace: LoadedWorkspace, revision_id: str
                 ) -> tuple[LoadedWorkspace, dict]:
        """Make a verified revision the active one and return the history."""
        if not isinstance(revision_id, str) or not revision_id.strip():
            raise ApiError(400, "the revision id is empty")
        if not self._lock.acquire(blocking=False):
            raise ApiError(409, BUSY_MESSAGE)
        try:
            return self._rollback(workspace, revision_id.strip())
        finally:
            self._lock.release()

    def _edit(self, workspace: LoadedWorkspace, instruction: str
              ) -> tuple[LoadedWorkspace | None, dict]:
        """Resolve the seams, run the edit and reload the workspace."""
        base_root = _base_root(workspace)
        settings: dict | None = None
        try:
            cfg = self._config_loader()
            settings = agent_settings(cfg)
            name = active_pack(cfg)
            manifests = discover(self._packs_root)
            if name not in manifests:
                raise ApiError(422, "the active pack is not installed")
            runner = load_runner(name, cfg, self._packs_root)
            seconds = timeout_s(cfg)
            api_key = read_api_key(settings)
            client = self._client_factory(settings, api_key)
            client = _SafeClient(client, _secrets(settings) + (api_key,))
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(422, _safe(str(exc), settings)) from None
        try:
            result = edit_part(base_root, instruction, client, runner, settings,
                               manifests[name], seconds)
        except RevisionError as exc:
            raise ApiError(409, _safe(str(exc), settings)) from None
        except Exception as exc:
            raise ApiError(422, _safe(str(exc), settings)) from None
        try:
            loaded = load_workspace(base_root)
        except Exception as exc:
            raise ApiError(422, _safe(str(exc), settings)) from None
        payload = {"revision_id": result.revision_id,
                   "parent_revision": result.parent_revision,
                   "active_revision": result.active_revision, "promoted": result.promoted,
                   "status": result.status, "stop_reason": result.generate.stop_reason,
                   "attempts": result.generate.attempts,
                   "error": _safe(result.error, settings)}
        return loaded, payload

    def _rollback(self, workspace: LoadedWorkspace, revision_id: str
                  ) -> tuple[LoadedWorkspace, dict]:
        """Select a verified revision and reload the workspace."""
        base_root = _base_root(workspace)
        try:
            rollback_revision(base_root, revision_id)
        except RevisionError:
            raise ApiError(400, ROLLBACK_REFUSED) from None
        except Exception:
            raise ApiError(422, ROLLBACK_REFUSED) from None
        try:
            loaded = load_workspace(base_root)
        except Exception:
            raise ApiError(422, ROLLBACK_REFUSED) from None
        return loaded, read_history_payload(loaded)


class _SafeClient:
    """A model client that keeps the credential out of every message.

    The core writes the error of a failed run into the manifest of the
    revision, so the credential is removed before the core ever sees it.
    """

    def __init__(self, client: ModelClient, secrets: tuple[str, ...]) -> None:
        """Take the client and the credential values that must not escape."""
        self._client = client
        self._secrets = secrets

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the client, or fail without the credential."""
        try:
            return self._client.complete(request)
        except Exception as exc:
            raise self._redacted(exc) from None

    def _redacted(self, exc: Exception) -> Exception:
        """Return the failure of the client without the credential in it."""
        message = str(exc)
        for secret in self._secrets:
            if secret:
                message = message.replace(secret, REDACTED)
        try:
            return type(exc)(message)
        except TypeError:
            return RuntimeError(message)


def _read_field(headers: Message[str, str], rfile: BufferedIOBase, bound_port: int,
                handler: object | None, field: str, missing: str) -> str:
    """Read one text field of one request, or refuse the request.

    The order is fixed: the local host and origin, then the handler, then the
    length of the body, and only then the body. A refusal never reads it.
    """
    reason = validate_local_request(
        headers.get("Host"), headers.get("Origin"), bound_port)
    if reason is not None:
        raise ApiError(403, reason)
    if handler is None:
        raise ApiError(503, missing)
    payload = _read_json(headers, rfile)
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, f"the {field} is missing or empty")
    return value.strip()


def _run(handler: EditHandler | RollbackHandler | None, workspace: LoadedWorkspace,
         value: str, missing: str) -> EditOutcome:
    """Run one mutating request and return what the endpoint answers."""
    if handler is None:
        return EditOutcome(503, {"error": missing})
    try:
        loaded, payload = handler(workspace, value)
    except ApiError as exc:
        return EditOutcome(exc.status, {"error": exc.message})
    except Exception:
        return EditOutcome(500, {"error": UNANSWERED})
    return EditOutcome(200, payload, loaded)


def _revision(entry) -> dict:
    """Return one revision of a history as a JSON-ready payload."""
    return {"id": entry.id, "parent": entry.parent, "kind": entry.kind,
            "status": entry.status, "stop_reason": entry.stop_reason,
            "instruction": entry.instruction, "attempts": entry.attempts,
            "prompt_version": entry.prompt_version}


def _base_root(workspace: LoadedWorkspace) -> Path:
    """Return the folder that owns the history of a workspace."""
    return Path(workspace.history_root or workspace.root)


def _read_json(headers: Message[str, str], rfile: BufferedIOBase) -> dict:
    """Read the body of one request and return the JSON object it holds."""
    length = _content_length(headers)
    try:
        payload = json.loads(rfile.read(length).decode("utf-8"))
    except UnicodeDecodeError:
        raise ApiError(400, "the request body is not UTF-8") from None
    except ValueError:
        raise ApiError(400, "the request body is not JSON") from None
    if not isinstance(payload, dict):
        raise ApiError(400, "the request body is not a JSON object")
    return payload


def _default_client_factory(settings: dict, api_key: str) -> ModelClient:
    """Build the model client of the configuration, on the server only."""
    return HttpModelClient.from_settings(settings, api_key)
