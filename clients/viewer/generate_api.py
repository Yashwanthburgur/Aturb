"""The prompt-to-3D endpoint of the viewer client.

The endpoint turns a natural-language requirement into a new workspace. It
holds the structural check of the local host and origin, the safe reading of
the request body, and the server-side generation service.

The service calls the existing expectation-free generation of the core into a
fresh timestamped workspace and writes its manifest. It never creates a task,
an answer or an expectation, and it never scores anything. The provider
credential is read from the environment variable the configuration names and
it is removed from every message the endpoint answers.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from email.message import Message
from io import BufferedIOBase
from pathlib import Path
from urllib.parse import urlsplit

from aturb.agent.config import agent_settings, read_api_key
from aturb.agent.generate_cli import DEFAULT_OUT_ROOT, STAMP_FORMAT, write_generate_manifest
from aturb.agent.model import HttpModelClient
from aturb.agent.types import ModelClient
from aturb.config import active_pack, load_config, timeout_s
from aturb.packs import default_packs_root, discover, load_runner
from clients.viewer.http_utils import (
    MAX_BODY_BYTES as MAX_BODY_BYTES,
)
from clients.viewer.http_utils import (
    ApiError,
    read_json_object,
    sanitize_message,
)
from clients.viewer.workspace import LoadedWorkspace, load_workspace

LOCAL_HOSTS = ("127.0.0.1", "localhost")
LOCAL_REFUSAL = "the request did not come from the local viewer"
NO_HANDLER = "generation is not available"

GenerateHandler = Callable[[str], tuple[LoadedWorkspace | None, dict]]


@dataclass(frozen=True)
class GenerateOutcome:
    """What one generation produced: the status, the body and the workspace."""

    status: int
    payload: dict
    workspace: LoadedWorkspace | None = None


def validate_local_request(
    host_header: str | None,
    origin_header: str | None,
    bound_port: int,
) -> str | None:
    """Return None when the request is local, or a short refusal reason."""
    reason = _address_reason(host_header, bound_port, origin=False)
    if reason is not None:
        return reason
    return _address_reason(origin_header, bound_port, origin=True)


def read_requirement(
    headers: Message[str, str],
    rfile: BufferedIOBase,
    bound_port: int,
    handler: GenerateHandler | None,
) -> str:
    """Read the requirement of one request, or refuse the request.

    The order is fixed: the local host and origin, then the handler, then the
    length of the body, and only then the body. A refusal never reads it.
    """
    reason = validate_local_request(
        headers.get("Host"), headers.get("Origin"), bound_port)
    if reason is not None:
        raise ApiError(403, reason)
    if handler is None:
        raise ApiError(503, NO_HANDLER)
    payload = read_json_object(headers, rfile)
    requirement = payload.get("requirement")
    if not isinstance(requirement, str) or not requirement.strip():
        raise ApiError(400, "the requirement is missing or empty")
    return requirement.strip()


def run_generation(
    handler: GenerateHandler | None,
    requirement: str,
) -> GenerateOutcome:
    """Run one generation and return what the endpoint answers.

    A busy service answers 409, a generation that could not be prepared
    answers 422, and an unexpected failure answers 500.
    """
    if handler is None:
        return GenerateOutcome(503, {"error": NO_HANDLER})
    try:
        loaded, payload = handler(requirement)
    except ApiError as exc:
        return GenerateOutcome(exc.status, {"error": exc.message})
    except Exception:
        return GenerateOutcome(500, {"error": "the request could not be answered"})
    return GenerateOutcome(200, payload, loaded)


class GenerateService:
    """The server-side generation service of the viewer.

    The configuration, the pack, the runner and the model client are resolved
    when a request arrives, never when the viewer starts. One generation runs
    at a time: a second request is refused instead of being queued.
    """

    def __init__(self, *, config_loader: Callable[[], dict] = load_config,
                 config_path: Path | None = None,
                 packs_root: Path | None = None,
                 client_factory: Callable[[dict, str],
                                          ModelClient] | None = None,
                 out_root: Path = DEFAULT_OUT_ROOT) -> None:
        """Take the seams the tests replace and the folder the workspaces go to."""
        self._config_loader = config_loader
        self._config_path = (Path(config_path)
                             if config_path is not None else None)
        self._packs_root = (Path(packs_root) if packs_root is not None
                            else default_packs_root())
        self._client_factory = client_factory or _default_client_factory
        self._out_root = Path(out_root)
        self._lock = threading.Lock()

    def __call__(self, requirement: str) -> tuple[LoadedWorkspace | None, dict]:
        """Generate one part into a fresh workspace and return it."""
        if not isinstance(requirement, str) or not requirement.strip():
            raise ApiError(400, "the requirement is empty")
        if not self._lock.acquire(blocking=False):
            raise ApiError(409, "a generation is already running")
        try:
            return self._generate(requirement.strip())
        finally:
            self._lock.release()

    def _generate(self, requirement: str) -> tuple[LoadedWorkspace | None, dict]:
        """Resolve the seams, run the generation and write the manifest."""
        from aturb.agent.generate import DEFAULT_PART_ID, generate_part

        settings: dict | None = None
        try:
            cfg = self._load_config()
            settings = agent_settings(cfg)
            name = active_pack(cfg)
            manifests = discover(self._packs_root)
            if name not in manifests:
                raise ApiError(422, "the active pack is not installed")
            runner = load_runner(name, cfg, self._packs_root)
            seconds = timeout_s(cfg)
            api_key = read_api_key(settings)
            client = self._client_factory(settings, api_key)
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(422, sanitize_message(str(exc), settings)) from None
        workspace = self._allocate_workspace()
        result = generate_part(
            requirement, workspace, client, runner, settings, manifests[name],
            seconds, part_id=DEFAULT_PART_ID)
        result = replace(result, error=sanitize_message(
            result.error, settings))
        try:
            write_generate_manifest(result)
            loaded = load_workspace(result.workspace)
        except Exception as exc:
            raise ApiError(422, sanitize_message(str(exc), settings)) from None
        payload = {"workspace": result.workspace.name, "status": result.status,
                   "stop_reason": result.stop_reason, "part_id": result.part_id,
                   "attempts": result.attempts, "error": result.error}
        return loaded, payload

    def _load_config(self) -> dict:
        """Return the configuration of the service.

        The path of the command line wins over the loader of the tests, so a
        viewer that was started with a configuration file uses that file.
        """
        if self._config_path is not None:
            return load_config(self._config_path)
        return self._config_loader()

    def _allocate_workspace(self) -> Path:
        """Return a fresh timestamped folder under the output root."""
        stamp = datetime.now().strftime(STAMP_FORMAT)
        candidate = self._out_root / stamp
        suffix = 1
        while candidate.exists():
            candidate = self._out_root / f"{stamp}_{suffix}"
            suffix += 1
        return candidate


def _default_client_factory(settings: dict, api_key: str) -> ModelClient:
    """Build the model client of the configuration, on the server only."""
    return HttpModelClient.from_settings(settings, api_key)


def _address_reason(value: str | None, bound_port: int, origin: bool) -> str | None:
    """Return the refusal reason of one address header, or None when it is local.

    A Host header is required and names the address without a scheme. An
    Origin header is optional and names it with the http scheme.
    """
    if value is None:
        return None if origin else LOCAL_REFUSAL
    if not isinstance(value, str) or not value or _has_forbidden(value):
        return LOCAL_REFUSAL
    if origin:
        if value.strip().lower() == "null" or "@" in value:
            return LOCAL_REFUSAL
        text = value
    else:
        if any(token in value for token in ("@", "/", "?", "#", "://")):
            return LOCAL_REFUSAL
        text = f"http://{value}"
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        return LOCAL_REFUSAL
    if parts.scheme.lower() != "http":
        return LOCAL_REFUSAL
    if parts.username is not None or parts.password is not None:
        return LOCAL_REFUSAL
    if parts.path or parts.query or parts.fragment:
        return LOCAL_REFUSAL
    hostname = (parts.hostname or "").lower()
    if hostname not in LOCAL_HOSTS or port != bound_port:
        return LOCAL_REFUSAL
    if parts.netloc.lower() != f"{hostname}:{bound_port}":
        return LOCAL_REFUSAL
    return None


def _has_forbidden(value: str) -> bool:
    """True when a header holds whitespace or a control character."""
    return any(char.isspace() or ord(char) < 0x20 or ord(char) == 0x7F for char in value)
