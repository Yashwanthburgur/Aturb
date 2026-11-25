"""Offline tests for the prompt-to-3D endpoint of the viewer.

Every test runs against a real loopback server with a fake model client and
the stub pack. No test leaves the machine and no test calls a provider.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import threading
from pathlib import Path

import pytest

from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from clients.viewer.generate_api import MAX_BODY_BYTES, GenerateService
from clients.viewer.server import ViewerServer
from clients.viewer.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKS_ROOT = REPO_ROOT / "packs"
SECRET = "TEST_SECRET_KEY_12345"
GOOD = """# Units: millimetres
# --- PARAMS ---
LENGTH_MM = 120.0
WIDTH_MM = 60.0
# --- END PARAMS ---
"""

FOREIGN_HOST = ["evil.example:{port}", "127.0.0.1:{other}", "localhost:{other}",
                "127.0.0.1:{port}@evil.example", "http://127.0.0.1:{port}",
                "127.0.0.1:{port}/path", "127.0.0.1:{port}?x=1",
                "127.0.0.1:{port}#frag", "127.0.0.1", "", None]
FOREIGN_ORIGIN = ["https://127.0.0.1:{port}", "https://localhost:{port}",
                  "http://127.0.0.1:{other}", "http://localhost:{other}",
                  "http://127.0.0.1:{port}@evil.example", "http://127.0.0.1:{port}/",
                  "http://127.0.0.1:{port}/path", "http://127.0.0.1:{port}?x=1",
                  "http://127.0.0.1:{port}#frag", "null", "", "not a url"]
BAD_BODIES = [b"", b"   ", b"not json", b"[]", b"\xff\xfe", b'{"requirement": 7}',
              b'{"requirement": ""}', b'{"requirement": "   "}', b"{}"]


class _FakeClient:
    """A model client that answers from a canned text."""

    def __init__(self, answer: str = GOOD, *, fail: bool = False):
        self.answer = answer
        self.fail = fail

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the canned text, or fail with the secret."""
        if self.fail:
            raise AgentError(f"the provider refused the key {SECRET}")
        return ModelResponse(text=self.answer, input_tokens=100, output_tokens=50)


def _config() -> dict:
    """Return the configuration of the offline tests."""
    return {"active_pack": "stub", "timeouts": {"build_s": 60},
            "agent": {"model": "fake-model", "api_key_env": "ATURB_AGENT_API_KEY"}}


def _service(tmp_path: Path, client: _FakeClient | None = None) -> GenerateService:
    """Return a generation service that never leaves the machine."""
    return GenerateService(
        config_loader=_config, packs_root=PACKS_ROOT,
        client_factory=lambda settings, api_key: client or _FakeClient(),
        out_root=tmp_path / "out")


def _write_workspace(root: Path) -> Path:
    """Write a minimal workspace with a manifest and return its folder."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "result.toml").write_text(
        'status = "ok"\npart_id = "part0001"\nstop_reason = "built"\n',
        encoding="utf-8")
    return root


@contextlib.contextmanager
def _serving(workspace: Path, handler):
    """Serve a workspace with a handler and stop the server afterwards."""
    instance = ViewerServer(load_workspace(workspace),
                            0, generate_handler=handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Serve a workspace with the real generation service."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    with _serving(_write_workspace(tmp_path / "open"), _service(tmp_path)) as live:
        yield live


@pytest.fixture
def recorder(tmp_path):
    """Serve a workspace with a handler that only records the calls."""
    calls: list[str] = []

    def handler(requirement: str):
        calls.append(requirement)
        return None, {"workspace": "recorded", "status": "ok", "stop_reason": "built",
                      "part_id": "part0001", "attempts": 1, "error": ""}

    with _serving(_write_workspace(tmp_path / "open"), handler) as live:
        yield live, calls


def _post(server: ViewerServer, *, host: str | None = None,
          origin: str | None = None, length: str | None = None,
          body: bytes = b"", path: str = "/api/generate",
          omit_length: bool = False) -> tuple[int, bytes]:
    """Send one POST request and return the status and the answer."""
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.bound_port, timeout=20)
    try:
        connection.putrequest("POST", path, skip_host=True)
        if host is not None:
            connection.putheader("Host", host)
        if origin is not None:
            connection.putheader("Origin", origin)
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


def test_a_local_request_generates_a_part_and_opens_it(server, tmp_path):
    """A local request generates a part and the viewer serves it."""
    port = server.bound_port
    body = json.dumps({"requirement": "A plate 120 mm by 60 mm."}).encode()
    status, payload = _post(server, host=f"127.0.0.1:{port}",
                            origin=f"http://127.0.0.1:{port}", body=body)
    answer = json.loads(payload)
    assert status == 200
    assert (answer["status"], answer["stop_reason"]) == ("ok", "built")
    assert (answer["part_id"], answer["attempts"]) == ("part0001", 1)
    assert answer["error"] == ""
    workspace = tmp_path / "out" / answer["workspace"]
    assert workspace.is_dir()
    names = {path.name for path in workspace.rglob("*")}
    assert not names & {"task.toml", "answer.toml", "expect"}
    code, _, raw = _get(server, "/api/manifest")
    assert code == 200
    assert json.loads(raw)["part_id"] == "part0001"
    code, _, raw = _get(server, "/api/mesh")
    assert code == 200
    assert json.loads(raw)["vertex_count"] > 0


def test_the_localhost_name_of_the_bound_port_is_accepted(recorder):
    """The localhost name of the bound port is a local request."""
    server, calls = recorder
    port = server.bound_port
    body = json.dumps({"requirement": "a plate"}).encode()
    status, _ = _post(server, host=f"localhost:{port}",
                      origin=f"http://localhost:{port}", body=body)
    assert status == 200
    assert calls == ["a plate"]


@pytest.mark.parametrize("header,value",
                         [("Host", v) for v in FOREIGN_HOST]
                         + [("Origin", v) for v in FOREIGN_ORIGIN])
def test_a_foreign_address_is_refused(recorder, header, value):
    """A Host or an Origin header that is not the bound address is refused."""
    server, calls = recorder
    port = server.bound_port
    headers: dict[str, str | None] = {
        "Host": f"127.0.0.1:{port}", "Origin": f"http://127.0.0.1:{port}"}
    headers[header] = (value.format(port=port, other=port + 1)
                       if value is not None else None)
    status, payload = _post(server, host=headers["Host"], origin=headers["Origin"],
                            length="20")
    assert status == 403
    assert "error" in json.loads(payload)
    assert calls == []


@pytest.mark.parametrize("length", ["abc", "-5", str(MAX_BODY_BYTES + 1)])
def test_a_foreign_host_is_refused_before_the_body_is_read(recorder, length):
    """A foreign host is refused before the length and the body are read."""
    server, calls = recorder
    status, _ = _post(server, host=f"evil.example:{server.bound_port}",
                      length=length)
    assert status == 403
    assert calls == []


@pytest.mark.parametrize("length,expected", [
    (str(MAX_BODY_BYTES + 1), 413), ("abc", 400), ("-5", 400)])
def test_a_bad_content_length_is_refused(recorder, length, expected):
    """A bad Content-Length is refused and the handler is never called."""
    server, calls = recorder
    status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                            length=length)
    assert status == expected
    assert "error" in json.loads(payload)
    assert calls == []


def test_a_request_without_a_content_length_is_refused(recorder):
    """A request without a Content-Length is refused."""
    server, calls = recorder
    status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                            omit_length=True)
    assert status == 411
    assert "error" in json.loads(payload)
    assert calls == []


@pytest.mark.parametrize("body", BAD_BODIES)
def test_a_bad_requirement_is_refused(recorder, body):
    """A body without a usable requirement is refused."""
    server, calls = recorder
    status, payload = _post(server, host=f"127.0.0.1:{server.bound_port}",
                            body=body)
    assert status == 400
    assert "error" in json.loads(payload)
    assert calls == []


def test_an_unknown_post_path_is_refused(recorder):
    """A POST to another path is refused."""
    server, calls = recorder
    status, _ = _post(server, host=f"127.0.0.1:{server.bound_port}",
                      body=b"{}", path="/api/other")
    assert status == 404
    assert calls == []


def test_a_failed_generation_answers_cleanly_and_hides_the_credential(
        tmp_path, monkeypatch):
    """A failed generation answers with the status and without a secret."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", SECRET)
    service = _service(tmp_path, _FakeClient(fail=True))
    with _serving(_write_workspace(tmp_path / "open"), service) as server:
        port = server.bound_port
        body = json.dumps({"requirement": "A plate."}).encode()
        status, payload = _post(server, host=f"127.0.0.1:{port}", body=body)
        answer = json.loads(payload)
        assert status == 200
        assert (answer["status"], answer["stop_reason"]) == (
            "error", "model_error")
        assert SECRET not in payload.decode()
        assert str(tmp_path) not in payload.decode()
        workspace = tmp_path / "out" / answer["workspace"]
        assert (workspace / "result.toml").is_file()
        code, _, raw = _get(server, "/api/manifest")
        assert code == 200
        assert SECRET not in raw.decode()


def test_the_page_loads_the_prompt_script(server):
    """The page loads the prompt script and the script is served."""
    code, kind, raw = _get(server, "/")
    assert code == 200
    assert kind == "text/html; charset=utf-8"
    assert b"/prompt.js" in raw
    code, kind, raw = _get(server, "/prompt.js")
    assert code == 200
    assert kind == "application/javascript; charset=utf-8"
    assert b"AturbApp" in raw
