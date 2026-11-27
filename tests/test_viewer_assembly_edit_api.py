"""Tests for the assembly edit endpoints of the viewer.

The stub pack builds every part, so the pipeline runs without a CAD.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import threading
from pathlib import Path

import pytest

from aturb.agent.types import ModelRequest, ModelResponse
from aturb.assembly.build import build_assembly
from aturb.packs import default_packs_root, load_runner
from clients.viewer.assembly_edit_api import AssemblyEditService
from clients.viewer.http_utils import MAX_BODY_BYTES
from clients.viewer.server import create_server, serve_in_thread
from clients.viewer.workspace import load_workspace

PART_TEXT = "# stub part\n"
UPDATED_TEXT = "# updated part\n"
KEY_ENV = "ATURB_TEST_KEY"
CONFIG = ('active_pack = "stub"\n[packs.stub]\n[timeouts]\nbuild_s = 60\n'
          f'[agent]\nmodel = "test-model"\napi_key_env = "{KEY_ENV}"\n')
MANIFEST = """assembly_id = "asm0001"
name = "Two plates"
[[components]]
name = "plate"
part_id = "plt0001"
position = [0.0, 0.0, 0.0]
[[components]]
name = "plate_top"
part_id = "plt0002"
position = [0.0, 0.0, 6.0]
[[mates]]
part_a = "plate"
part_b = "plate_top"
min_clearance_mm = 0.5
max_clearance_mm = 1.5"""
ANSWER = "# === PART: plt0002 ===\n# updated part\n# === END PART: plt0002 ===\n"


class FakeClient:
    """A model client that answers with one canned text."""

    def __init__(self, answers: list[str]) -> None:
        """Take the answers, one per call."""
        self.answers = list(answers)

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the next canned text."""
        text = self.answers.pop(0) if self.answers else ""
        return ModelResponse(text=text, input_tokens=10, output_tokens=20)


def _project(tmp_path: Path) -> Path:
    """Write a project with two stub parts and one assembly manifest."""
    project = tmp_path / "project"
    (project / "parts").mkdir(parents=True)
    for name in ("plt0001_base_plate", "plt0002_top_plate"):
        (project / "parts" /
         f"{name}.stub").write_text(PART_TEXT, encoding="utf-8")
    (project / "assemblies").mkdir(parents=True)
    (project / "assemblies" / "asm0001.toml").write_text(MANIFEST, encoding="utf-8")
    return project


def _config(tmp_path: Path) -> Path:
    """Write a configuration that names the stub pack."""
    path = tmp_path / "aturb.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def _out_dir(project: Path) -> Path:
    """Return the output folder of the assembly of a project."""
    return project / "out" / "assemblies" / "asm0001"


def _built_project(tmp_path: Path) -> Path:
    """Write a project and build its assembly, so the workspace exists."""
    project = _project(tmp_path)
    runner = load_runner("stub", {"packs": {}}, default_packs_root())
    result = build_assembly(
        project, project / "assemblies" / "asm0001.toml", runner)
    assert result.status == "ok", result.error
    return project


def _service(project: Path, config: Path, client: FakeClient,
             lock: threading.Lock | None = None) -> AssemblyEditService:
    """Return the assembly service of a project with a fake model client."""
    return AssemblyEditService(_out_dir(project), config, lock=lock,
                               client_factory=lambda settings, api_key: client)


@pytest.fixture
def assembly(tmp_path, monkeypatch):
    """Return the project, the service and the workspace of one assembly."""
    monkeypatch.setenv(KEY_ENV, "secret-value")
    project = _built_project(tmp_path)
    service = _service(project, _config(tmp_path), FakeClient([ANSWER]))
    return project, service, load_workspace(_out_dir(project))


@contextlib.contextmanager
def _serving(workspace, service=None):
    """Serve a workspace over loopback and stop the server afterwards."""
    server = create_server(workspace, port=0, assembly_edit_service=service)
    thread = serve_in_thread(server)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(server, method: str, path: str, body: str = "", headers=None,
             host: str | None = None) -> tuple[int, dict]:
    """Answer one request with the exact headers and return the answer."""
    address, port = server.server_address[:2]
    connection = http.client.HTTPConnection(
        str(address), int(port), timeout=20)
    try:
        connection.putrequest(method, path, skip_host=host is not None)
        connection.putheader("Host", host or f"{address}:{port}")
        if method == "POST":
            connection.putheader("Content-Type", "application/json")
        for name, value in headers or []:
            connection.putheader(name, value)
        connection.endheaders()
        if body:
            connection.send(body.encode("utf-8"))
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _send(server, path: str, payload: dict, headers=None, host=None):
    """Answer a POST request with a JSON body and return the answer."""
    body = json.dumps(payload)
    sent = [("Content-Length", str(len(body)))] + list(headers or [])
    return _request(server, "POST", path, body, sent, host)


def _refusal(server, case: str) -> tuple[int, dict]:
    """Answer the request of one refusal case and return the answer."""
    edit = "/api/assembly/edit"
    if case == "host":
        return _send(server, edit, {"instruction": "raise"}, host="evil.example:80")
    if case == "origin":
        return _send(server, edit, {"instruction": "raise"},
                     headers=[("Origin", "http://evil.example")])
    if case == "no-length":
        return _request(server, "POST", edit)
    raw = {"negative-length": ("", "-1"), "not-a-number": ("", "abc"),
           "too-large": ("not json", str(MAX_BODY_BYTES + 1)),
           "not-json": ("not json", "8"), "not-an-object": ("[1, 2]", "6")}
    if case in raw:
        body, length = raw[case]
        return _request(server, "POST", edit, body, [("Content-Length", length)])
    if case == "empty-instruction":
        return _send(server, edit, {"instruction": "  "})
    return _send(server, "/api/assembly/rollback", {"revision_id": ""})


def test_the_history_endpoint_answers_the_revisions_of_the_assembly(assembly):
    """The history of the assembly is served as JSON."""
    _, service, workspace = assembly
    with _serving(workspace, service) as server:
        status, payload = _request(server, "GET", "/api/assembly/history")
    assert status == 200
    assert payload["assembly_id"] == "asm0001"
    assert payload["has_history"] is False
    assert payload["revisions"] == []


def test_the_edit_endpoint_edits_the_assembly_and_records_a_revision(assembly):
    """An edit of the assembly is promoted and recorded as a revision."""
    project, service, workspace = assembly
    part = project / "parts" / "plt0002_top_plate.stub"
    with _serving(workspace, service) as server:
        status, payload = _send(server, "/api/assembly/edit",
                                {"instruction": "raise the top plate"})
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["promoted"] is True
    assert payload["attempts"] == 1
    assert payload["updated_parts"] == ["plt0002"]
    assert payload["revision_id"] == "r0002"
    assert part.read_text(encoding="utf-8") == UPDATED_TEXT
    assert str(project) not in json.dumps(payload)


def test_the_rollback_endpoint_restores_a_verified_revision(assembly):
    """A rollback brings back the parts of the first revision."""
    project, service, workspace = assembly
    part = project / "parts" / "plt0002_top_plate.stub"
    with _serving(workspace, service) as server:
        _send(server, "/api/assembly/edit",
              {"instruction": "raise the top plate"})
        status, payload = _send(
            server, "/api/assembly/rollback", {"revision_id": "r0001"})
    assert status == 200
    assert payload["active_revision"] == "r0001"
    assert part.read_text(encoding="utf-8") == PART_TEXT


@pytest.mark.parametrize("case,status", [
    ("host", 403),
    ("origin", 403),
    ("no-length", 411),
    ("negative-length", 400),
    ("not-a-number", 400),
    ("too-large", 413),
    ("not-json", 400),
    ("not-an-object", 400),
    ("empty-instruction", 400),
    ("empty-revision", 400),
])
def test_a_refused_request_answers_with_its_own_status(assembly, case, status):
    """Every refused request answers with its own status and an error."""
    _, service, workspace = assembly
    with _serving(workspace, service) as server:
        answer, payload = _refusal(server, case)
    assert answer == status
    assert "error" in payload


def test_the_body_limit_is_the_same_on_every_endpoint(assembly):
    """The unified limit accepts 65_536 bytes and refuses 65_537."""
    _, service, workspace = assembly
    empty = '{"revision_id": ""}'
    body = empty + " " * (MAX_BODY_BYTES - len(empty))
    with _serving(workspace, service) as server:
        accepted, payload = _request(
            server, "POST", "/api/assembly/rollback", body,
            [("Content-Length", str(MAX_BODY_BYTES))])
        refused, _ = _request(
            server, "POST", "/api/assembly/rollback", "not json",
            [("Content-Length", str(MAX_BODY_BYTES + 1))])
    assert MAX_BODY_BYTES == 65_536
    assert accepted == 400
    assert "revision_id" in payload["error"]
    assert refused == 413


def test_the_endpoints_are_not_available_without_a_service(assembly):
    """A viewer without the assembly service refuses both endpoints."""
    _, _, workspace = assembly
    with _serving(workspace) as server:
        status, _ = _request(server, "GET", "/api/assembly/history")
        answer, _ = _send(server, "/api/assembly/edit",
                          {"instruction": "raise the top plate"})
    assert status == 503
    assert answer == 503


def test_a_workspace_without_an_assembly_is_refused(assembly, tmp_path):
    """A workspace that holds no assembly is refused."""
    _, _, workspace = assembly
    service = AssemblyEditService(
        tmp_path, _config(tmp_path),
        client_factory=lambda settings, api_key: FakeClient([ANSWER]))
    with _serving(workspace, service) as server:
        status, _ = _send(server, "/api/assembly/edit",
                          {"instruction": "raise the top plate"})
    assert status == 400


def test_a_busy_service_refuses_the_request(assembly, tmp_path):
    """A service that is already busy refuses the request."""
    project, _, workspace = assembly
    lock = threading.Lock()
    lock.acquire()
    service = _service(project, _config(tmp_path), FakeClient([ANSWER]), lock)
    try:
        with _serving(workspace, service) as server:
            status, _ = _send(server, "/api/assembly/edit",
                              {"instruction": "raise the top plate"})
    finally:
        lock.release()
    assert status == 409
