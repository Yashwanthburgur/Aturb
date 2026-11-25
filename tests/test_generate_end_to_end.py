"""End-to-end generation tests with canned clients and no network."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from aturb.agent.types import ModelRequest, ModelResponse
from aturb.cli import main
from aturb.verify.holes import find_holes
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
TASKS = REPO_ROOT / "evals" / "tasks"
PART_ID = "part0001"
GOOD = """# Units: millimetres
# --- PARAMS ---
LENGTH_MM = 100.0
# --- END PARAMS ---
"""
BROKEN = "def build(doc):\n    return (\n"
REQUIREMENT = "Build a 100 x 50 x 6 mm plate with one 8 mm centred through-hole"
CANDIDATE = '''"""Centred plate with one through-hole. Units: millimetres.

The plate is centred on the origin in X and Y and spans Z = 0 to THICKNESS_MM.
"""
# --- PARAMS ---
LENGTH_MM = 100.0
WIDTH_MM = 50.0
THICKNESS_MM = 6.0
HOLE_DIAMETER_MM = 8.0
# --- END PARAMS ---


def build(doc):
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "PlateSketch")
    x, y = LENGTH_MM / 2, WIDTH_MM / 2
    points = [App.Vector(-x, -y, 0), App.Vector(x, -y, 0),
              App.Vector(x, y, 0), App.Vector(-x, y, 0)]
    for index in range(4):
        sketch.addGeometry(
            Part.LineSegment(points[index], points[(index + 1) % 4]), False)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = THICKNESS_MM

    hole = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole.Placement = App.Placement(
        App.Vector(0, 0, THICKNESS_MM), App.Rotation())
    hole.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1),
        HOLE_DIAMETER_MM / 2), False)
    pocket = body.newObject("PartDesign::Pocket", "Holes")
    pocket.Profile = hole
    pocket.Type = "ThroughAll"
    return body
'''


class _FakeClient:
    def __init__(self, answers: str | list[str]):
        self.answers = [answers] if isinstance(answers, str) else answers
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.answers) - 1)
        return ModelResponse(
            text=self.answers[index], input_tokens=120, output_tokens=45)


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "aturb.local.toml"
    path.write_text(
        'active_pack = "stub"\n[packs.stub]\n[timeouts]\nbuild_s = 60\n'
        '[agent]\nmodel = "canned-model"\n', encoding="utf-8")
    return path


def _manifest(out_dir: Path) -> dict:
    with (out_dir / "result.toml").open("rb") as handle:
        return tomllib.load(handle)


def _assert_no_evaluation_files(out_dir: Path) -> None:
    for path in out_dir.rglob("*"):
        assert path.name not in {"task.toml", "answer.toml", "expect"}


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*")) if path.is_file()
    }


def test_offline_happy_path_writes_source_step_and_manifest(
        tmp_path, monkeypatch, capsys):
    client = _FakeClient(GOOD)
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    out_dir = tmp_path / "generated"
    code = main(["generate", "Build a plate", "--out", str(out_dir),
                 "--config", str(_config(tmp_path))])
    assert code == 0
    data = _manifest(out_dir)
    assert data["status"] == "ok" and data["stop_reason"] == "built"
    assert data["attempts"] == 1
    assert (out_dir / data["part_file"]).is_file()
    assert (out_dir / data["step_file"]).is_file()
    assert "Measured geometry:" in capsys.readouterr().out
    _assert_no_evaluation_files(out_dir)


def test_offline_repair_path_records_two_attempts(tmp_path, monkeypatch):
    client = _FakeClient(["# STUB: fail=syntax_error\n", GOOD])
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    out_dir = tmp_path / "generated"
    code = main(["generate", "Build a plate", "--out", str(out_dir),
                 "--config", str(_config(tmp_path))])
    data = _manifest(out_dir)
    assert code == 0 and data["attempts"] == 2
    assert data["stop_reason"] == "built"
    assert "## Repair" in client.requests[1].prompt
    _assert_no_evaluation_files(out_dir)


def test_prompt_file_works_and_missing_prompt_exits_two(
        tmp_path, monkeypatch, capsys):
    client = _FakeClient(GOOD)
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Build from a prompt file", encoding="utf-8")
    config = _config(tmp_path)
    out_dir = tmp_path / "generated"
    code = main(["generate", "--prompt-file", str(prompt), "--out", str(out_dir),
                 "--config", str(config)])
    assert code == 0
    assert "Build from a prompt file" in client.requests[0].prompt
    capsys.readouterr()
    code = main(["generate", "--out", str(tmp_path / "missing"),
                 "--config", str(config)])
    assert code == 2
    assert "exactly one" in capsys.readouterr().out


@pytest.mark.freecad
def test_real_backend_repairs_and_measures_a_centred_through_hole(
        tmp_path, monkeypatch, capsys):
    before = _snapshot(TASKS)
    client = _FakeClient([BROKEN, CANDIDATE])
    monkeypatch.setattr("aturb.cli._model_client", lambda settings: client)
    out_dir = tmp_path / "gen_fc"
    code = main(["generate", REQUIREMENT, "--out", str(out_dir),
                 "--config", str(LOCAL_CONFIG)])
    report = capsys.readouterr().out
    assert code == 0, report
    data = _manifest(out_dir)
    assert data["attempts"] == 2 and data["stop_reason"] == "built"
    assert data["status"] == "ok" and data["build_status"] == "ok"
    assert "Build: failed (syntax_error)" in client.requests[1].prompt
    assert "Previous candidate:" in client.requests[1].prompt
    step = out_dir / data["step_file"]
    model = load_step(step)
    assert model.is_valid and model.is_single_solid
    assert model.volume == pytest.approx(29698.4071, abs=0.01)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx((100.0, 50.0, 6.0))
    holes = find_holes(model)
    assert len(holes) == 1
    assert holes[0].diameter == pytest.approx(8.0)
    assert holes[0].x == pytest.approx(0.0, abs=1e-6)
    assert holes[0].y == pytest.approx(0.0, abs=1e-6)
    assert data["hole_count"] == 1 and data["is_valid"] is True
    for key in ("part_file", "step_file", "native_file"):
        assert not Path(data[key]).is_absolute()
        assert (out_dir / data[key]).is_file()
    assert "volume: 29698.407105 mm^3" in report
    assert "diameter 8 mm" in report
    _assert_no_evaluation_files(out_dir)
    assert _snapshot(TASKS) == before
