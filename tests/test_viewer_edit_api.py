"""Offline tests for the history, edit and rollback endpoints of the viewer.

Every test runs against a real loopback server with a fake model client and
the stub pack. No test leaves the machine and no test calls a provider.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.generate import generate_part
from aturb.agent.generate_cli import write_generate_manifest
from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.packs import load_manifest
from clients.viewer.edit_api import EditService
from clients.viewer.generate_api import MAX_BODY_BYTES, ApiError
from clients.viewer.server import ViewerServer
from clients.viewer.workspace import load_workspace
from packs.stub.runner import StubRunner

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKS_ROOT = REPO_ROOT / "packs"
STATIC_DIR = REPO_ROOT / "clients" / "viewer" / "static"
STUB_PACK = load_manifest(PACKS_ROOT / "stub" / "pack.toml")
SECRET = "TEST_EDIT_SECRET_999"
GOOD = "# Units: millimetres\nLENGTH_MM = 120.0\nWIDTH_MM = 60.0\n"
BAD = "# STUB: fail=syntax_error\n"
INSTRUCTION = "Make the plate 10 mm thick"
PATHS = ["/api/edit", "/api/rollback"]
FOREIGN_HOST = ["evil.example:{port}", "127.0.0.1:{other}", "localhost:{other}",
                "127.0.0.1:{port}@evil.example", "http://127.0.0.1:{port}",
                "127.0.0.1:{port}/path", "127.0.0.1:{port}?x=1",
                "127.0.0.1:{port}#frag", "127.0.0.1", "", None]
FOREIGN_ORIGIN = ["https://127.0.0.1:{port}", "https://localhost:{port}",
                  "http://127.0.0.1:{other}", "http://localhost:{other}",
                  "http://127.0.0.1:{port}@evil.example", "http://127.0.0.1:{port}/",
                  "http://127.0.0.1:{port}/path", "http://127.0.0.1:{port}?x=1",
                  "http://127.0.0.1:{port}#frag", "null", "", "not a url"]
EDIT_BODIES = [b"", b"   ", b"not json", b"[]", b"\xff\xfe", b'{"instruction": 7}',
               b'{"instruction": ""}', b'{"instruction": "   "}', b"{}"]
ROLLBACK_BODIES = [b"", b"   ", b"not json", b"[]", b"\xff\xfe",
                   b'{"revision_id": 7}', b'{"revision_id": ""}',
                   b'{"revision_id": "   "}', b"{}"]


class _FakeClient:
    """A model client that answers from canned text."""

    def __init__(self, answers: str | list[str] = GOOD, *, fail: bool = False):
        self.answers = [answers] if isinstance(answers, str) else list(answers)
        self.fail = fail
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the canned text, or fail with the secret."""
        self.requests.append(request)
        if self.fail:
            raise AgentError(f"the provider refused the key {SECRET}")
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return ModelResponse(text=self.answers[index], input_tokens=100, output_tokens=50)


def _config(max_attempts: int = 3) -> dict:
    """Return the configuration of the offline tests."""
    return {"active_pack": "stub", "timeouts": {"build_s": 60},
            "agent": {"model": "fake-model", "api_key_env": "ATURB_AGENT_API_KEY",
                      "max_attempts": max_attempts}}


def _service(client: _FakeClient | None = None, *, max_attempts: int = 3,
             lock: threading.Lock | None = None) -> EditService:
    """Return an edit service that never leaves the machine."""
    return EditService(
        config_loader=lambda: _config(max_attempts), packs_root=PACKS_ROOT,
        client_factory=lambda settings, api_key: client or _FakeClient(),
        lock=lock)


def _workspace(tmp_path: Path, *, fail: bool = False) -> Path:
    """Build a plain Phase 8 workspace with the stub pack."""
    workspace = tmp_path / "workspace"
    result = generate_part(
        "Build a plate", workspace, _FakeClient(BAD if fail else GOOD),
        StubRunner(settings={}, pack_dir=STUB_PACK.pack_dir),
        agent_settings({"agent": {"model": "fake-model"}}), STUB_PACK,
        timeout_s=60, part_id="part0001")
    write_generate_manifest(result)
    return workspace


@contextlib.contextmanager
def _serving(workspace: Path, *, edit_handler=None, rollback_handler=None):
    """Serve a workspace with the given handlers and stop the server after."""
    instance = ViewerServer(load_workspace(workspace), 0,
                            edit_handler=edit_handler, rollback_handler=rollback_handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


def _post(server: ViewerServer, *, host=None, origin=None, length=None,
          body: bytes = b"", path: str = "/api/edit",
          omit_length: bool = False) -> tuple[int, bytes]:
    """Send one POST request and return the status and the answer."""
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.bound_port, timeout=20)
    try:
        connection.putrequest("POST", path, skip_host=True)
        for name, value in (("Host", host), ("Origin", origin)):
            if value is not None:
                connection.putheader(name, value)
        connection.putheader("Content-Type", "application/json")
        if not omit_length:
            connection.putheader(
                "Content-Length", length if length is not None else str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def _get(server: ViewerServer, path: str) -> tuple[int, str, bytes]:
    """Answer one GET request and return the status, the type and the body."""
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), int(port), timeout=20)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return (response.status, response.getheader("Content-Type") or "", response.read())
    finally:
        connection.close()


def _edit(server: ViewerServer, instruction: str = INSTRUCTION) -> tuple[int, dict]:
    """Post one edit to the server and return the status and the answer."""
    body = json.dumps({"instruction": instruction}).encode("utf-8")
    status, payload = _post(
        server, host=f"127.0.0.1:{server.bound_port}", body=body)
    return status, json.loads(payload)


def _rollback(server: ViewerServer, revision_id: str) -> tuple[int, dict]:
    """Post one rollback to the server and return the status and the answer."""
    body = json.dumps({"revision_id": revision_id}).encode("utf-8")
    status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                            body=body, path="/api/rollback")
    return status, json.loads(payload)


def _history(server: ViewerServer) -> dict:
    """Return the revision history the server answers."""
    code, _, raw = _get(server, "/api/history")
    assert code == 200
    return json.loads(raw)


def _manifest(server: ViewerServer) -> dict:
    """Return the manifest the server answers."""
    code, _, raw = _get(server, "/api/manifest")
    assert code == 200
    return json.loads(raw)


@pytest.fixture
def recorder(tmp_path):
    """Serve a workspace with handlers that only record the calls."""
    calls: list[tuple[str, str]] = []

    def edit(workspace, instruction):
        calls.append(("edit", instruction))
        return None, {"revision_id": "r0002"}

    def rollback(workspace, revision_id):
        calls.append(("rollback", revision_id))
        return None, {"active_revision": "r0001"}

    with _serving(_workspace(tmp_path), edit_handler=edit,
                  rollback_handler=rollback) as server:
        yield server, calls


@pytest.mark.parametrize("fail,editable", [(False, True), (True, False)])
def test_the_history_of_a_workspace_without_revisions(tmp_path, fail, editable):
    """A workspace without a history says whether it can be edited."""
    with _serving(_workspace(tmp_path, fail=fail)) as server:
        answer = _history(server)
    assert answer["has_history"] is False
    assert answer["active_revision"] is None
    assert answer["editable"] is editable
    assert answer["revisions"] == []


def test_an_edit_bootstraps_a_history_and_promotes_a_revision(tmp_path, monkeypatch):
    """A local edit builds r0002 and the viewer follows it."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path)
    service = _service()
    with _serving(workspace, edit_handler=service.edit,
                  rollback_handler=service.rollback) as server:
        status, answer = _edit(server)
        assert status == 200
        assert answer["promoted"] is True
        assert answer["status"] == "ok"
        assert answer["revision_id"] == "r0002"
        assert answer["parent_revision"] == "r0001"
        assert answer["active_revision"] == "r0002"
        assert answer["stop_reason"] == "built"
        assert answer["attempts"] == 1
        assert answer["error"] == ""
        assert server.workspace.active_revision == "r0002"
        assert server.workspace.root == (
            workspace / "revisions" / "r0002").resolve()
        assert _manifest(server)["status"] == "ok"
        code, _, raw = _get(server, "/api/mesh")
        assert code == 200
        assert json.loads(raw)["vertex_count"] > 0
        history = _history(server)
        assert history["has_history"] is True
        assert history["active_revision"] == "r0002"
        assert [entry["id"]
                for entry in history["revisions"]] == ["r0001", "r0002"]
        assert history["revisions"][1]["kind"] == "edit"
        assert history["revisions"][1]["instruction"] == INSTRUCTION


def test_a_failed_edit_keeps_the_active_revision(tmp_path, monkeypatch):
    """A failed edit is recorded and the verified part stays active."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path)
    service = _service(_FakeClient([GOOD, BAD]), max_attempts=1)
    with _serving(workspace, edit_handler=service.edit,
                  rollback_handler=service.rollback) as server:
        assert _edit(server)[1]["active_revision"] == "r0002"
        status, answer = _edit(server, "Break it")
        assert status == 200
        assert answer["promoted"] is False
        assert answer["status"] == "error"
        assert answer["revision_id"] == "r0003"
        assert answer["parent_revision"] == "r0002"
        assert answer["active_revision"] == "r0002"
        assert server.workspace.active_revision == "r0002"
        assert _manifest(server)["status"] == "ok"
        code, _, raw = _get(server, "/api/mesh")
        assert code == 200
        assert json.loads(raw)["vertex_count"] > 0
        history = _history(server)
        assert history["active_revision"] == "r0002"
        assert history["revisions"][-1]["id"] == "r0003"
        assert history["revisions"][-1]["status"] == "error"


def test_a_rollback_selects_an_earlier_revision(tmp_path, monkeypatch):
    """A rollback makes an earlier revision active and refuses the rest."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path)
    service = _service(_FakeClient([GOOD, BAD]), max_attempts=1)
    with _serving(workspace, edit_handler=service.edit,
                  rollback_handler=service.rollback) as server:
        assert _edit(server)[1]["active_revision"] == "r0002"
        assert _edit(server, "Break it")[1]["active_revision"] == "r0002"
        for revision in ("r0003", "r9999"):
            status, answer = _rollback(server, revision)
            assert status in (400, 422)
            assert "error" in answer
        status, answer = _rollback(server, "r0001")
        assert status == 200
        assert answer["active_revision"] == "r0001"
        assert answer["has_history"] is True
        assert server.workspace.active_revision == "r0001"
        assert _manifest(server)["status"] == "ok"
        assert _history(server)["active_revision"] == "r0001"


def test_a_failed_workspace_is_never_edited(tmp_path, monkeypatch):
    """A failed generation is refused and nothing is written."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path, fail=True)
    before = {path.relative_to(workspace).as_posix(): path.read_bytes()
              for path in sorted(workspace.rglob("*")) if path.is_file()}
    service = _service()
    with _serving(workspace, edit_handler=service.edit,
                  rollback_handler=service.rollback) as server:
        status, answer = _edit(server)
    after = {path.relative_to(workspace).as_posix(): path.read_bytes()
             for path in sorted(workspace.rglob("*")) if path.is_file()}
    assert status in (409, 422)
    assert "error" in answer
    assert after == before
    assert not (workspace / "history.toml").exists()
    assert not (workspace / "revisions").exists()


def test_a_revisioned_workspace_opens_on_its_active_revision(tmp_path, monkeypatch):
    """A rollback survives a restart of the viewer."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path)
    service = _service()
    with _serving(workspace, edit_handler=service.edit,
                  rollback_handler=service.rollback) as server:
        assert _edit(server)[1]["active_revision"] == "r0002"
        assert _rollback(server, "r0001")[1]["active_revision"] == "r0001"
    loaded = load_workspace(workspace)
    assert loaded.active_revision == "r0001"
    assert loaded.history_root == workspace.resolve()
    assert loaded.root == (workspace / "revisions" / "r0001").resolve()
    with _serving(workspace) as server:
        assert server.workspace.active_revision == "r0001"
        assert _manifest(server)["status"] == "ok"
        assert _history(server)["active_revision"] == "r0001"


def test_a_busy_service_refuses_a_second_edit(tmp_path, monkeypatch):
    """One edit runs at a time: a second request is refused with 409."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path)
    lock = threading.Lock()
    service = _service(lock=lock)
    lock.acquire()
    try:
        with pytest.raises(ApiError) as info:
            service.edit(load_workspace(workspace), INSTRUCTION)
    finally:
        lock.release()
    assert info.value.status == 409


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("header,value",
                         [("Host", v) for v in FOREIGN_HOST]
                         + [("Origin", v) for v in FOREIGN_ORIGIN])
def test_a_foreign_address_is_refused(recorder, path, header, value):
    """A Host or an Origin header that is not the bound address is refused."""
    server, calls = recorder
    port = server.bound_port
    headers: dict[str, str | None] = {
        "Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}"}
    headers[header] = (value.format(port=port, other=port + 1)
                       if value is not None else None)
    status, payload = _post(server, host=headers["Host"], origin=headers["Origin"],
                            length="20", path=path)
    assert status == 403
    assert "error" in json.loads(payload)
    assert calls == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("length", ["abc", "-5", str(MAX_BODY_BYTES + 1)])
def test_a_foreign_host_is_refused_before_the_body_is_read(recorder, path, length):
    """A foreign host is refused before the length and the body are read."""
    server, calls = recorder
    status, _ = _post(server, host=f"evil.example:{server.bound_port}",
                      length=length, path=path)
    assert status == 403
    assert calls == []


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("length,expected", [
    (str(MAX_BODY_BYTES + 1), 413), ("abc", 400), ("-5", 400)])
def test_a_bad_content_length_is_refused(recorder, path, length, expected):
    """A bad Content-Length is refused and the handler is never called."""
    server, calls = recorder
    status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                            length=length, path=path)
    assert status == expected
    assert "error" in json.loads(payload)
    assert calls == []


@pytest.mark.parametrize("path", PATHS)
def test_a_request_without_a_content_length_is_refused(recorder, path):
    """A request without a Content-Length is refused."""
    server, calls = recorder
    status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                            omit_length=True, path=path)
    assert status == 411
    assert "error" in json.loads(payload)
    assert calls == []


@pytest.mark.parametrize("path,bodies", [("/api/edit", EDIT_BODIES),
                                         ("/api/rollback", ROLLBACK_BODIES)])
def test_a_bad_body_is_refused(recorder, path, bodies):
    """A body without a usable field is refused and never reaches the handler."""
    server, calls = recorder
    for body in bodies:
        status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                                body=body, path=path)
        assert status == 400
        assert "error" in json.loads(payload)
        assert calls == []


@pytest.mark.parametrize("path", PATHS)
def test_a_viewer_without_the_service_answers_503(tmp_path, path):
    """A read-only viewer answers 503 and reads no body."""
    with _serving(_workspace(tmp_path)) as server:
        status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                                body=b"{}", path=path)
    assert status == 503
    assert "error" in json.loads(payload)


def test_a_failed_edit_hides_the_credential_and_the_path(tmp_path, monkeypatch):
    """A failed edit answers and writes without the credential."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    workspace = _workspace(tmp_path)
    service = _service(_FakeClient(fail=True))
    with _serving(workspace, edit_handler=service.edit,
                  rollback_handler=service.rollback) as server:
        status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                                body=json.dumps({"instruction": INSTRUCTION}).encode())
        text = payload.decode("utf-8")
        assert status == 200
        assert SECRET not in text
        assert str(tmp_path) not in text
        assert SECRET not in json.dumps(_manifest(server))
    for name in ("result.toml", "history.toml"):
        for path in workspace.rglob(name):
            assert SECRET not in path.read_text(encoding="utf-8")


def test_the_page_loads_the_history_script(tmp_path):
    """The page loads the history script and the script is served."""
    with _serving(_workspace(tmp_path)) as server:
        code, kind, raw = _get(server, "/")
        assert code == 200
        assert kind == "text/html; charset=utf-8"
        assert b"/history.js" in raw
        code, kind, raw = _get(server, "/history.js")
    assert code == 200
    assert kind == "application/javascript; charset=utf-8"
    assert b"AturbHistory" in raw


@pytest.mark.parametrize("name", ["inspector.js", "prompt.js", "history.js"])
def test_the_browser_scripts_pass_the_syntax_check(name: str):
    """Every browser script of the viewer passes the node syntax check."""
    if shutil.which("node") is None:
        pytest.skip("node is not installed on this machine")
    result = subprocess.run(["node", "--check", str(STATIC_DIR / name)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
