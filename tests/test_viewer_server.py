"""Tests for the loopback-only read-only viewer server.

Every test talks to a real server over the loopback address, served in a
background thread and stopped in a finally block. No test leaves the machine.
"""

from __future__ import annotations

import contextlib
import http.client
import json
from pathlib import Path

import pytest

from aturb.agent.record import toml_string
from clients.viewer.server import (
    DEFAULT_PORT,
    LOOPBACK_HOST,
    PORT_ENV,
    ViewerServer,
    create_server,
    resolve_port,
    serve_in_thread,
)
from clients.viewer.workspace import LoadedWorkspace, load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

PART_BYTES = b"# candidate\n"
NATIVE_BYTES = b"native bytes"
STATIC_ASSETS = {
    "index.html": b"<!doctype html><title>viewer</title>\n",
    "viewer.css": b"body { margin: 0; }\n",
    "viewer.js": b"const viewer = 1;\n",
}
ARTIFACT_NAMES = {
    "part_file": "part.py",
    "step_file": "part.step",
    "native_file": "part.native",
}


def _write_workspace(root: Path, **artifacts: bytes) -> LoadedWorkspace:
    """Write a workspace with the given artifacts and load it.

    The key is the kind of the artifact and the value is its bytes.
    """
    root.mkdir(parents=True, exist_ok=True)
    fields = {"status": "ok", "part_id": "part0001", "stop_reason": "built"}
    for kind, body in artifacts.items():
        name = ARTIFACT_NAMES[kind]
        (root / name).write_bytes(body)
        fields[kind] = name
    lines = [f"{key} = {toml_string(value)}" for key, value in fields.items()]
    (root / "result.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_workspace(root)


def _write_static(root: Path) -> Path:
    """Write the bundled browser assets of a test."""
    root.mkdir(parents=True, exist_ok=True)
    for name, body in STATIC_ASSETS.items():
        (root / name).write_bytes(body)
    return root


@contextlib.contextmanager
def _serving(workspace: LoadedWorkspace, static_dir: Path):
    """Serve a workspace over loopback and stop the server afterwards."""
    server = create_server(workspace, port=0, static_dir=static_dir)
    thread = serve_in_thread(server)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(server: ViewerServer, path: str) -> tuple[int, dict[str, str], bytes]:
    """Answer one GET request; the path is sent as it is written."""
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), int(port), timeout=10)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        return response.status, dict(response.getheaders()), body
    finally:
        connection.close()


@pytest.fixture
def served(tmp_path):
    """Serve a workspace with three artifacts and the bundled browser assets."""
    workspace = _write_workspace(tmp_path / "workspace", part_file=PART_BYTES,
                                 step_file=FIXTURE.read_bytes(),
                                 native_file=NATIVE_BYTES)
    with _serving(workspace, _write_static(tmp_path / "static")) as server:
        yield server


def test_the_server_binds_to_the_loopback_address(tmp_path):
    """The server binds to 127.0.0.1 on a port the operating system chose."""
    workspace = _write_workspace(tmp_path / "workspace")
    with _serving(workspace, _write_static(tmp_path / "static")) as server:
        host, port = server.server_address[:2]
        assert host == LOOPBACK_HOST == "127.0.0.1"
        assert port != 0
        assert server.url == f"http://127.0.0.1:{port}/"


def test_resolve_port_reads_the_environment():
    """The port comes from the environment variable when it names one."""
    assert resolve_port({PORT_ENV: "8123"}) == 8123
    assert resolve_port({PORT_ENV: "0"}) == 0
    assert resolve_port({PORT_ENV: ""}) == DEFAULT_PORT == 0
    assert resolve_port({}) == DEFAULT_PORT == 0


@pytest.mark.parametrize("raw", ["abc", "-1", "65536", "12.5", "80 81"])
def test_resolve_port_refuses_an_invalid_port(raw):
    """A port that is not a number in range is refused."""
    with pytest.raises(ValueError):
        resolve_port({PORT_ENV: raw})


def test_a_non_loopback_host_is_refused(tmp_path):
    """A host that is not a loopback address is refused."""
    workspace = _write_workspace(tmp_path / "workspace")
    with pytest.raises(ValueError):
        create_server(workspace, port=0, static_dir=tmp_path / "static",
                      host="0.0.0.0")


@pytest.mark.parametrize("path,name,content_type", [
    ("/", "index.html", "text/html; charset=utf-8"),
    ("/viewer.css", "viewer.css", "text/css; charset=utf-8"),
    ("/viewer.js", "viewer.js", "application/javascript; charset=utf-8"),
])
def test_the_page_and_the_assets_carry_their_mime_type(
        served, path, name, content_type):
    """The page and an asset carry the MIME type their extension implies."""
    status, headers, body = _get(served, path)

    assert status == 200
    assert headers["Content-Type"] == content_type
    assert body == STATIC_ASSETS[name]


@pytest.mark.parametrize("path", ["/missing.css", "/result.toml", "/secret.txt"])
def test_an_unknown_asset_is_refused(served, path):
    """An asset that is not bundled is refused."""
    status, headers, body = _get(served, path)

    assert status == 404
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert "error" in json.loads(body)


@pytest.mark.parametrize("path", [
    "/../secret.txt",
    "/%2e%2e/secret.txt",
    "/..%2fsecret.txt",
    "/%2e%2e%2fsecret.txt",
    "/sub/../secret.txt",
    "/..\\secret.txt",
])
def test_a_traversal_asset_is_refused(served, path):
    """An asset path that leaves the static directory is refused."""
    status, _, body = _get(served, path)

    assert status == 404
    assert "error" in json.loads(body)


def test_the_manifest_is_served(served):
    """The manifest of the open workspace is served as JSON."""
    status, headers, body = _get(served, "/api/manifest")

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
    assert payload["status"] == "ok"
    assert payload["part_file"] == "part.py"
    assert payload["step_file"] == "part.step"
    assert payload["native_file"] == "part.native"


def test_the_mesh_is_served(served):
    """The mesh of the exported STEP is served as JSON."""
    status, headers, body = _get(served, "/api/mesh")

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
    assert payload["vertex_count"] == 1036
    assert payload["triangle_count"] == 1028
    assert len(payload["positions"]) == 3 * payload["vertex_count"]
    assert len(payload["indices"]) == 3 * payload["triangle_count"]


@pytest.mark.parametrize("kind,name,expected", [
    ("part_file", "part.py", PART_BYTES),
    ("step_file", "part.step", FIXTURE.read_bytes()),
    ("native_file", "part.native", NATIVE_BYTES),
])
def test_a_declared_artifact_is_served(served, kind, name, expected):
    """A declared artifact is served with its bytes and a download name."""
    status, headers, body = _get(served, f"/api/files/{kind}")

    assert status == 200
    assert body == expected
    assert headers["Content-Disposition"] == f'attachment; filename="{name}"'
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_an_unknown_kind_is_refused(served):
    """A kind that the manifest does not declare is refused."""
    status, _, body = _get(served, "/api/files/secret.txt")

    assert status == 404
    assert "error" in json.loads(body)


def test_an_escaping_artifact_is_refused(tmp_path):
    """An artifact that leaves the workspace is refused with 403."""
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.step"
    outside.write_bytes(b"outside")
    workspace = LoadedWorkspace(
        root=root.resolve(),
        manifest={"status": "ok", "step_file": "../outside.step"},
        artifacts={"part_file": None, "step_file": outside.resolve(),
                   "native_file": None},
    )
    with _serving(workspace, _write_static(tmp_path / "static")) as server:
        for path in ("/api/files/step_file", "/api/mesh"):
            status, _, body = _get(server, path)
            assert status == 403
            assert "error" in json.loads(body)


def test_a_failed_workspace_answers_without_a_step(tmp_path):
    """A workspace without a STEP file answers 200 and 404, never an error."""
    workspace = _write_workspace(tmp_path / "workspace", part_file=PART_BYTES)
    with _serving(workspace, _write_static(tmp_path / "static")) as server:
        status, _, _ = _get(server, "/")
        assert status == 200
        status, _, body = _get(server, "/api/manifest")
        assert status == 200
        assert json.loads(body)["status"] == "ok"
        for path in ("/api/mesh", "/api/files/step_file"):
            status, _, body = _get(server, path)
            assert status == 404
            assert "error" in json.loads(body)


def test_a_broken_step_answers_422(tmp_path):
    """A STEP file that cannot be meshed answers 422 and never an error."""
    workspace = _write_workspace(
        tmp_path / "workspace", step_file=b"not a STEP\n")
    with _serving(workspace, _write_static(tmp_path / "static")) as server:
        status, _, _ = _get(server, "/api/manifest")
        assert status == 200
        status, _, body = _get(server, "/api/mesh")
        assert status == 422
        assert "error" in json.loads(body)


def test_the_error_bodies_name_no_path_of_the_host(tmp_path):
    """An error body never leaks a path of the host."""
    workspace = _write_workspace(
        tmp_path / "workspace", step_file=b"not a STEP\n")
    with _serving(workspace, _write_static(tmp_path / "static")) as server:
        for path in ("/api/mesh", "/api/files/step_file", "/missing.css"):
            _, _, body = _get(server, path)
            text = body.decode("utf-8")
            assert str(tmp_path) not in text
            assert "C:\\" not in text and "/Users/" not in text


def test_the_server_never_writes_into_the_workspace(served, tmp_path):
    """The read-only routes leave the workspace exactly as it was."""
    folder = tmp_path / "workspace"

    def snapshot():
        return {path.name: path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}

    before = snapshot()
    for path in ("/", "/api/manifest", "/api/mesh", "/api/files/part_file"):
        _get(served, path)
    assert snapshot() == before
