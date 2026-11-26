"""Tests for the engineering readouts of the viewer and for coupled edits.

The offline suite uses the stub pack and a canned client, so it never calls a
model and never needs a CAD. The marked test uses the real backend pack with a
canned client, so it builds real geometry and measures it.

The flanged hub of the marked test is a bushing: a flange, a hub tube on top of
it, a bore through both and four bolt holes on a pitch circle. The card names
the hub by its bore in the edit and by its outside in the first revision, so
the test names both diameters and measures what the card asks for: the
ligament between the bore and the bolt holes, and the wall to the edge.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import math
import threading
import tomllib
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.edit import edit_part
from aturb.agent.generate import generate_part
from aturb.agent.generate_cli import write_generate_manifest
from aturb.agent.revisions import active_revision_dir
from aturb.agent.types import ModelRequest, ModelResponse
from aturb.config import load_config, timeout_s
from aturb.packs import default_packs_root, load_manifest, load_runner
from aturb.verify.engineering import DfmFinding, EngineeringReport, analyze_step
from aturb.verify.step import load_step
from clients.viewer.edit_api import EditService
from clients.viewer.server import ViewerServer
from clients.viewer.workspace import load_workspace
from packs.stub.runner import StubRunner

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKS_ROOT = REPO_ROOT / "packs"
STUB_PACK = load_manifest(PACKS_ROOT / "stub" / "pack.toml")
FREECAD_PACK = load_manifest(PACKS_ROOT / "freecad" / "pack.toml")
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
PART_ID = "part0001"
FLANGE_THICKNESS_MM = 10.0
HUB_HEIGHT_MM = 30.0
BOLT_HOLE_DIA_MM = 6.0
BOLT_HOLE_COUNT = 4
INSTRUCTION = "Make the hub 56 mm, the bolt circle 68 mm and the flange 90 mm"

PLATE = '''"""A plate. Units: millimetres."""
# --- PARAMS ---
LENGTH_MM = 120.0
WIDTH_MM = 60.0
THICKNESS_MM = 5.0
# --- END PARAMS ---
'''


class _FakeClient:
    """A model client that answers with canned candidates and records prompts."""

    def __init__(self, answers: str | list[str] = PLATE):
        self.answers = [answers] if isinstance(answers, str) else list(answers)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return ModelResponse(
            text=self.answers[index], input_tokens=100, output_tokens=50)


def _runner() -> StubRunner:
    """Return the runner of the stub pack."""
    return StubRunner(settings={}, pack_dir=STUB_PACK.pack_dir)


def _settings(**overrides) -> dict:
    """Return the agent settings of the tests."""
    settings = agent_settings({"agent": {"model": "fake-model"}})
    settings.update(overrides)
    return settings


def _config() -> dict:
    """Return the configuration of the offline viewer tests."""
    return {"active_pack": "stub", "timeouts": {"build_s": 60},
            "agent": {"model": "fake-model", "api_key_env": "ATURB_AGENT_API_KEY",
                      "max_attempts": 3}}


def _workspace(tmp_path: Path) -> Path:
    """Build a plain workspace with the stub pack."""
    workspace = tmp_path / "workspace"
    result = generate_part(
        "Build a plate", workspace, _FakeClient(PLATE), _runner(), _settings(),
        STUB_PACK, timeout_s=60, part_id=PART_ID)
    write_generate_manifest(result)
    assert result.status == "ok", result.error
    return workspace


def _plain_workspace(root: Path, step: bytes | None) -> Path:
    """Write a workspace that declares a STEP file, or none at all."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "part.py").write_text(PLATE, encoding="utf-8")
    lines = ['status = "ok"', 'part_id = "part0001"', 'stop_reason = "built"',
             'part_file = "part.py"']
    if step is not None:
        (root / "part.step").write_bytes(step)
        lines.append('step_file = "part.step"')
    (root / "result.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _step_of(folder: Path) -> Path:
    """Return the exported STEP of the manifest of a folder."""
    with (folder / "result.toml").open("rb") as handle:
        manifest = tomllib.load(handle)
    return folder / manifest["step_file"]


@contextlib.contextmanager
def _serving(workspace: Path, service: EditService | None = None):
    """Serve a workspace over loopback and stop the server afterwards."""
    instance = ViewerServer(
        load_workspace(workspace), 0,
        edit_handler=service.edit if service else None,
        rollback_handler=service.rollback if service else None)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


def _get(server: ViewerServer, path: str) -> tuple[int, dict]:
    """Answer one GET request and return the status and the body."""
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), int(port), timeout=20)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _post(server: ViewerServer, path: str, body: dict) -> tuple[int, dict]:
    """Send one POST request and return the status and the answer."""
    raw = json.dumps(body).encode("utf-8")
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.bound_port, timeout=20)
    try:
        connection.putrequest("POST", path, skip_host=True)
        connection.putheader("Host", f"127.0.0.1:{server.bound_port}")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(raw)))
        connection.endheaders(raw)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_the_edit_prompt_carries_the_current_engineering_facts(tmp_path):
    """The edit prompt holds the measured clearances and the parameters."""
    workspace = _workspace(tmp_path)
    client = _FakeClient(PLATE)
    edit = edit_part(workspace, "Make it 10 mm thick", client, _runner(),
                     _settings(), STUB_PACK, timeout_s=60)
    assert edit.promoted is True, edit.error
    prompt = client.requests[0].prompt
    assert "min_hole_spacing: 70.0 mm" in prompt
    assert "min_edge_margin: 15.0 mm" in prompt
    assert "surface_area: 16200.0 mm^2" in prompt
    assert "Current parameters:" in prompt
    assert "- LENGTH_MM = 120.0" in prompt


def test_the_edit_prompt_carries_the_advisory_findings(tmp_path, monkeypatch):
    """The advisory findings of the current part reach the edit prompt."""
    workspace = _workspace(tmp_path)
    report = EngineeringReport(
        bbox_min=(-60.0, -30.0, -2.5), bbox_max=(60.0, 30.0, 2.5),
        bbox_size=(120.0, 60.0, 5.0), volume=35214.6, surface_area=16200.0,
        center_of_mass=(0.0, 0.0, 0.0), hole_count=2,
        min_hole_spacing_mm=1.0, min_edge_margin_mm=15.0,
        dfm_findings=(DfmFinding(
            "DFM2", "warning",
            "the holes at (0.0, 0.0) and (70.0, 0.0) leave a ligament of 1.000 mm"),))
    monkeypatch.setattr("aturb.agent.edit.analyze_step", lambda path: report)
    client = _FakeClient(PLATE)
    edit = edit_part(workspace, "Make it 10 mm thick", client, _runner(),
                     _settings(), STUB_PACK, timeout_s=60)
    assert edit.promoted is True, edit.error
    prompt = client.requests[0].prompt
    assert "min_hole_spacing: 1.0 mm" in prompt
    assert "DFM2 (warning): the holes at (0.0, 0.0) and (70.0, 0.0)" in prompt


def test_the_manifest_carries_the_engineering_facts(tmp_path):
    """The manifest of the viewer carries the measured engineering facts."""
    workspace = _workspace(tmp_path)
    with _serving(workspace) as server:
        status, payload = _get(server, "/api/manifest")
    assert status == 200
    engineering = payload["engineering"]
    assert engineering["surface_area"] == pytest.approx(16200.0)
    assert engineering["min_hole_spacing_mm"] == 70.0
    assert engineering["min_edge_margin_mm"] == 15.0
    assert engineering["hole_count"] == 2
    assert engineering["dfm_findings"] == []
    assert str(tmp_path) not in json.dumps(payload)


def test_a_workspace_without_a_step_answers_no_engineering(tmp_path):
    """A workspace with no STEP file answers None and never fails."""
    workspace = _plain_workspace(tmp_path / "workspace", None)
    with _serving(workspace) as server:
        status, payload = _get(server, "/api/manifest")
    assert status == 200
    assert payload["engineering"] is None


def test_a_step_that_is_not_a_step_answers_no_engineering(tmp_path):
    """A STEP file that cannot be read answers None and never fails."""
    workspace = _plain_workspace(tmp_path / "workspace", b"not a STEP\n")
    with _serving(workspace) as server:
        status, payload = _get(server, "/api/manifest")
    assert status == 200
    assert payload["engineering"] is None


def test_the_engineering_facts_follow_the_active_revision(tmp_path, monkeypatch):
    """The facts are measured from the STEP file of the active revision."""
    monkeypatch.setenv("ATURB_AGENT_API_KEY", "TEST_ENGINEERING_SECRET_999")
    workspace = _workspace(tmp_path)
    service = EditService(
        config_loader=_config, packs_root=PACKS_ROOT,
        client_factory=lambda settings, api_key: _FakeClient(PLATE))
    with _serving(workspace, service=service) as server:
        status, payload = _get(server, "/api/manifest")
        assert status == 200
        assert payload["engineering"]["min_hole_spacing_mm"] == 70.0
        code, answer = _post(server, "/api/edit", {"instruction": INSTRUCTION})
        assert code == 200, answer
        status, payload = _get(server, "/api/manifest")
        assert status == 200
        assert payload["engineering"]["min_hole_spacing_mm"] == 70.0
        active = active_revision_dir(workspace)
        (active / payload["step_file"]).write_bytes(b"not a STEP\n")
        status, payload = _get(server, "/api/manifest")
        assert status == 200
        assert payload["engineering"] is None
        code, answer = _post(server, "/api/rollback", {"revision_id": "r0001"})
        assert code == 200, answer
        status, payload = _get(server, "/api/manifest")
        assert status == 200
        assert payload["engineering"]["min_hole_spacing_mm"] == 70.0


def _hub_source(flange: float, hub_outer: float, hub_bore: float, pcd: float) -> str:
    """Return the source of the flanged hub with the given dimensions."""
    return f'''"""Flanged hub. Units: millimetres."""
# --- PARAMS ---
FLANGE_DIA_MM = {flange}
FLANGE_THICKNESS_MM = {FLANGE_THICKNESS_MM}
HUB_OUTER_DIA_MM = {hub_outer}
HUB_BORE_DIA_MM = {hub_bore}
HUB_HEIGHT_MM = {HUB_HEIGHT_MM}
BOLT_CIRCLE_DIA_MM = {pcd}
BOLT_HOLE_DIA_MM = {BOLT_HOLE_DIA_MM}
BOLT_HOLE_COUNT = {BOLT_HOLE_COUNT}
# --- END PARAMS ---


def build(doc):
    """Build the flanged hub in the given document and return the final object."""
    import FreeCAD as App
    import Part
    import math

    body = doc.addObject("PartDesign::Body", "Body")

    flange_sketch = body.newObject("Sketcher::SketchObject", "FlangeSketch")
    flange_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), FLANGE_DIA_MM / 2), False)
    flange = body.newObject("PartDesign::Pad", "Flange")
    flange.Profile = flange_sketch
    flange.Length = FLANGE_THICKNESS_MM

    hub_sketch = body.newObject("Sketcher::SketchObject", "HubSketch")
    hub_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    hub_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), HUB_OUTER_DIA_MM / 2), False)
    hub = body.newObject("PartDesign::Pad", "Hub")
    hub.Profile = hub_sketch
    hub.Length = HUB_HEIGHT_MM

    bore_sketch = body.newObject("Sketcher::SketchObject", "BoreSketch")
    bore_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM + HUB_HEIGHT_MM), App.Rotation())
    bore_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), HUB_BORE_DIA_MM / 2), False)
    bore = body.newObject("PartDesign::Pocket", "Bore")
    bore.Profile = bore_sketch
    bore.Type = "ThroughAll"

    bolt_sketch = body.newObject("Sketcher::SketchObject", "BoltSketch")
    bolt_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    radius = BOLT_CIRCLE_DIA_MM / 2
    for index in range(BOLT_HOLE_COUNT):
        angle = 2 * math.pi * index / BOLT_HOLE_COUNT
        bolt_sketch.addGeometry(Part.Circle(
            App.Vector(radius * math.cos(angle), radius * math.sin(angle), 0),
            App.Vector(0, 0, 1), BOLT_HOLE_DIA_MM / 2), False)
    bolts = body.newObject("PartDesign::Pocket", "BoltHoles")
    bolts.Profile = bolt_sketch
    bolts.Type = "ThroughAll"

    return body
'''


def _hub_volume(flange: float, hub_outer: float, hub_bore: float) -> float:
    """Return the hand-calculated volume of the flanged hub."""
    flange_volume = math.pi * (flange / 2) ** 2 * FLANGE_THICKNESS_MM
    bore_in_flange = math.pi * (hub_bore / 2) ** 2 * FLANGE_THICKNESS_MM
    hub_volume = math.pi * (
        (hub_outer / 2) ** 2 - (hub_bore / 2) ** 2) * HUB_HEIGHT_MM
    bolt_volume = (BOLT_HOLE_COUNT * math.pi * (BOLT_HOLE_DIA_MM / 2) ** 2
                   * FLANGE_THICKNESS_MM)
    return flange_volume - bore_in_flange - bolt_volume + hub_volume


@pytest.mark.freecad
def test_a_real_coupled_edit_keeps_the_clearances_legal(tmp_path):
    """A coupled edit of a flanged hub keeps every clearance legal."""
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())
    workspace = tmp_path / "workspace"
    result = generate_part(
        "Build a flanged hub", workspace,
        _FakeClient(_hub_source(80.0, 40.0, 24.0, 60.0)), runner, _settings(),
        FREECAD_PACK, timeout_s=timeout_s(cfg), part_id=PART_ID)
    write_generate_manifest(result)
    assert result.status == "ok", result.error
    before = analyze_step(_step_of(workspace))
    assert before.min_hole_spacing_mm == pytest.approx(15.0)
    assert before.min_edge_margin_mm == pytest.approx(7.0)
    assert before.dfm_findings == ()
    edit = edit_part(
        workspace, INSTRUCTION, _FakeClient(
            _hub_source(90.0, 60.0, 56.0, 68.0)),
        runner, _settings(), FREECAD_PACK, timeout_s=timeout_s(cfg))
    assert edit.promoted is True, edit.error
    assert edit.active_revision == "r0002"
    step = _step_of(active_revision_dir(workspace))
    after = analyze_step(step)
    assert after.min_hole_spacing_mm == pytest.approx(3.0)
    assert after.min_edge_margin_mm == pytest.approx(8.0)
    assert after.dfm_findings == ()
    model = load_step(step)
    assert model.is_valid and model.is_single_solid
    assert model.volume == pytest.approx(
        _hub_volume(90.0, 60.0, 56.0), abs=0.05)
