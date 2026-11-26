"""Serve the open workspace over loopback-only HTTP.

The viewer is a local, single-user tool: the server binds to the loopback
address and it never writes into the workspace itself. The request never
carries a path: it names a kind, a browser asset or an endpoint, and the
server resolves all three itself. Every error is a structured JSON body that
names no path of the host.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit

from clients.viewer.edit_api import (
    EditHandler,
    RollbackHandler,
    read_edit_instruction,
    read_history_payload,
    read_rollback_revision,
    run_edit,
    run_rollback,
)
from clients.viewer.generate_api import (
    ApiError,
    GenerateHandler,
    read_requirement,
    run_generation,
)
from clients.viewer.mesh import MeshError, tessellate_step
from clients.viewer.workspace import (
    DECLARED_ARTIFACT_KINDS,
    ArtifactMissingError,
    LoadedWorkspace,
    WorkspaceError,
    resolve_artifact,
)

LOOPBACK_HOST = "127.0.0.1"  # starting default
DEFAULT_PORT = 0  # starting default
PORT_ENV = "ATURB_VIEW_PORT"
MAX_PORT = 65535
LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")

STATIC_DIR = Path(__file__).resolve().parent / "static"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

ENCODED_TRAVERSAL = ("%2e", "%2f", "%5c")
FILE_PREFIX = "/api/files/"
GENERATE_PATH = "/api/generate"
HISTORY_PATH = "/api/history"
EDIT_PATH = "/api/edit"
ROLLBACK_PATH = "/api/rollback"
ASSET_MISSING = "the requested asset is not available"


def resolve_port(env: Mapping[str, str] | None = None) -> int:
    """Return the port to bind, from the environment or from the default.

    ``ATURB_VIEW_PORT`` pins the port; without it the operating system chooses
    one. Raises ``ValueError`` when the variable names no port number.
    """
    source = os.environ if env is None else env
    raw = source.get(PORT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_PORT
    try:
        port = int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"{PORT_ENV} must be a port number, got {raw!r}") from exc
    if port < 0 or port > MAX_PORT:
        raise ValueError(
            f"{PORT_ENV} must be between 0 and {MAX_PORT}, got {port}")
    return port


class ViewerHandler(BaseHTTPRequestHandler):
    """The request handler of the viewer server.

    A request names a kind, an asset or an endpoint, never a path.
    """

    server_version = "ATURBViewer/1.0"
    protocol_version = "HTTP/1.1"
    _responded = False

    @property
    def viewer(self) -> "ViewerServer":
        """Return the viewer server that owns this handler."""
        return cast("ViewerServer", self.server)

    def version_string(self) -> str:
        """Return the server name without the version of the interpreter."""
        return self.server_version

    def log_message(self, fmt: str, *args) -> None:
        """Keep the request log quiet: the server is a local tool."""

    def do_GET(self) -> None:
        """Answer one read-only request."""
        self._responded = False
        raw_path = urlsplit(self.path).path
        try:
            if _has_encoded_traversal(raw_path):
                self._send_json(404, {"error": ASSET_MISSING})
                return
            path = unquote(raw_path)
            if path == "/":
                self._serve_asset("index.html")
            elif path == "/api/manifest":
                self._send_json(200, self.viewer.workspace.manifest)
            elif path == HISTORY_PATH:
                self._send_json(200, read_history_payload(
                    self.viewer.workspace))
            elif path == "/api/mesh":
                self._serve_mesh()
            elif path.startswith(FILE_PREFIX):
                self._serve_file(path[len(FILE_PREFIX):])
            else:
                self._serve_asset(path[1:])
        except Exception:
            if not self._responded:
                self._send_json(
                    500, {"error": "the request could not be answered"})

    def do_POST(self) -> None:
        """Answer one mutating request.

        The generation, the edit and the rollback endpoints exist. The local
        host and the local origin are checked before the body is read, so a
        request from another page never reaches a service. A refused request
        closes the connection, because its body is never read.
        """
        self._responded = False
        try:
            path = urlsplit(self.path).path
            if path == GENERATE_PATH:
                requirement = read_requirement(
                    self.headers, self.rfile, self.viewer.bound_port,
                    self.viewer.generate_handler)
                outcome = run_generation(
                    self.viewer.generate_handler, requirement)
            elif path == EDIT_PATH:
                instruction = read_edit_instruction(
                    self.headers, self.rfile, self.viewer.bound_port,
                    self.viewer.edit_handler)
                outcome = run_edit(
                    self.viewer.edit_handler, self.viewer.workspace, instruction)
            elif path == ROLLBACK_PATH:
                revision_id = read_rollback_revision(
                    self.headers, self.rfile, self.viewer.bound_port,
                    self.viewer.rollback_handler)
                outcome = run_rollback(
                    self.viewer.rollback_handler, self.viewer.workspace,
                    revision_id)
            else:
                raise ApiError(404, "unknown endpoint")
            if outcome.workspace is not None:
                self.viewer.set_workspace(outcome.workspace)
            self._send_json(outcome.status, outcome.payload)
        except ApiError as exc:
            self.close_connection = True
            self._send_json(exc.status, {"error": exc.message})
        except Exception:
            if not self._responded:
                self._send_json(
                    500, {"error": "the request could not be answered"})

    def _serve_asset(self, name: str) -> None:
        """Serve one bundled browser asset by name."""
        found = self._resolve_asset(name)
        if found is None:
            self._send_json(404, {"error": ASSET_MISSING})
            return
        target, content_type = found
        try:
            body = target.read_bytes()
        except OSError:
            self._send_json(404, {"error": ASSET_MISSING})
            return
        self._send_bytes(200, body, content_type)

    def _resolve_asset(self, name: str) -> tuple[Path, str] | None:
        """Return the bundled asset of a name and its MIME type, or None.

        The name is one file name: a separator, a parent component, an unknown
        extension, a missing file and an escaping symbolic link are refused.
        """
        if not name or name in {".", ".."}:
            return None
        if "/" in name or "\\" in name or Path(name).name != name:
            return None
        content_type = MIME_TYPES.get(Path(name).suffix.lower())
        if content_type is None:
            return None
        root = self.viewer.static_dir.resolve(strict=False)
        target = (root / name).resolve(strict=False)
        if target == root or not target.is_relative_to(root):
            return None
        if not target.is_file():
            return None
        return target, content_type

    def _serve_mesh(self) -> None:
        """Serve the mesh of the exported STEP of the open workspace."""
        try:
            step = resolve_artifact(self.viewer.workspace, "step_file")
        except ArtifactMissingError:
            self._send_json(
                404, {"error": "artifact 'step_file' is not available"})
            return
        except WorkspaceError:
            self._send_json(
                403, {"error": "artifact 'step_file' is not available"})
            return
        try:
            mesh = tessellate_step(step)
        except MeshError:
            self._send_json(
                422, {"error": "artifact 'step_file' cannot be meshed"})
            return
        self._send_json(200, mesh.to_dict())

    def _serve_file(self, kind: str) -> None:
        """Serve one declared artifact of the open workspace."""
        if kind not in DECLARED_ARTIFACT_KINDS:
            self._send_json(404, {"error": "unknown artifact kind"})
            return
        try:
            target = resolve_artifact(self.viewer.workspace, kind)
        except ArtifactMissingError:
            self._send_json(
                404, {"error": f"artifact '{kind}' is not available"})
            return
        except WorkspaceError:
            self._send_json(
                403, {"error": f"artifact '{kind}' is not available"})
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._send_json(
                404, {"error": f"artifact '{kind}' is not available"})
            return
        self._send_bytes(
            200, body, "application/octet-stream",
            {"Content-Disposition":
             f'attachment; filename="{_download_name(target)}"'})

    def _send_json(self, status: int, payload: dict) -> None:
        """Answer with a JSON body."""
        body = json.dumps(payload).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, body: bytes, content_type: str,
                    extra_headers: Mapping[str, str] | None = None) -> None:
        """Answer with a body of bytes."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self._responded = True
        self.wfile.write(body)
        self.wfile.flush()


class ViewerServer(ThreadingHTTPServer):
    """The loopback-only HTTP server of the viewer.

    It holds the open workspace, the directory of the bundled browser assets
    and the optional generation, edit and rollback services. The workspace can
    be swapped while the server runs.
    """

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, workspace: LoadedWorkspace, port: int = DEFAULT_PORT,
                 static_dir: Path | None = None, host: str = LOOPBACK_HOST,
                 generate_handler: GenerateHandler | None = None,
                 edit_handler: EditHandler | None = None,
                 rollback_handler: RollbackHandler | None = None):
        """Bind the server to the loopback address."""
        self.workspace = workspace
        self.static_dir = Path(
            static_dir) if static_dir is not None else STATIC_DIR
        self.generate_handler = generate_handler
        self.edit_handler = edit_handler
        self.rollback_handler = rollback_handler
        super().__init__((_check_loopback(host), port), ViewerHandler)

    @property
    def url(self) -> str:
        """Return the loopback URL the server is bound to."""
        host, port = self.server_address[:2]
        return f"http://{host}:{port}/"

    @property
    def bound_port(self) -> int:
        """Return the port the server is bound to."""
        return int(self.server_address[1])

    def set_workspace(self, workspace: LoadedWorkspace) -> None:
        """Open another workspace without restarting the server."""
        self.workspace = workspace


def create_server(
    workspace: LoadedWorkspace,
    port: int | None = None,
    static_dir: Path | None = None,
    host: str = LOOPBACK_HOST,
    generate_handler: GenerateHandler | None = None,
    edit_handler: EditHandler | None = None,
    rollback_handler: RollbackHandler | None = None,
) -> ViewerServer:
    """Bind the viewer server to the loopback address and return it.

    The port comes from the argument, the environment or the operating system.
    """
    chosen = resolve_port() if port is None else port
    if chosen < 0 or chosen > MAX_PORT:
        raise ValueError(
            f"the port must be between 0 and {MAX_PORT}, got {chosen}")
    return ViewerServer(workspace, chosen, static_dir, host, generate_handler,
                        edit_handler, rollback_handler)


def serve_in_thread(server: ViewerServer) -> threading.Thread:
    """Serve in a background thread and return the thread."""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def _check_loopback(host: str) -> str:
    """Return the host when it is a loopback address, and refuse the rest."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            f"the viewer binds to the loopback address only, got {host!r}")
    return host


def _has_encoded_traversal(raw_path: str) -> bool:
    """True when the raw path holds a percent-encoded dot or a separator."""
    lowered = raw_path.lower()
    return any(token in lowered for token in ENCODED_TRAVERSAL)


def _download_name(path: Path) -> str:
    """Return a safe download file name for an artifact."""
    name = path.name.replace('"', "_").replace("\\", "_")
    return name.replace("\r", "_").replace("\n", "_") or "artifact"
