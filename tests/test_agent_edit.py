"""Tests for iterative editing and the immutable revision history.

The offline suite uses the stub pack and a canned client, so it never calls a
model and never needs a design system. The marked test uses the real backend
pack with a canned client, so it builds real geometry and measures it.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.edit import compose_edit_requirement, edit_part
from aturb.agent.generate import generate_part
from aturb.agent.generate_cli import write_generate_manifest
from aturb.agent.revisions import (
    RevisionError,
    active_revision_dir,
    ensure_history,
    load_history,
    rollback_revision,
)
from aturb.agent.types import ModelRequest, ModelResponse
from aturb.config import load_config, timeout_s
from aturb.packs import default_packs_root, load_manifest, load_runner
from aturb.verify.step import load_step
from aturb.workspace.paths import PathEscapeError
from clients.viewer.workspace import load_workspace
from packs.stub.runner import StubRunner

REPO_ROOT = Path(__file__).resolve().parents[1]
STUB_PACK = load_manifest(REPO_ROOT / "packs" / "stub" / "pack.toml")
FREECAD_PACK = load_manifest(REPO_ROOT / "packs" / "freecad" / "pack.toml")
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
PART_ID = "part0001"
GOOD = "# Units: millimetres\nLENGTH_MM = 120.0\nWIDTH_MM = 60.0\n"
BAD = "# STUB: fail=syntax_error\n"
INSTRUCTION = "Make the plate 10 mm thick"


class _FakeClient:
    """A model client that answers with canned candidates and records prompts."""

    def __init__(self, answers: str | list[str] = GOOD):
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


def _workspace(tmp_path: Path) -> Path:
    """Build a plain Phase 8 workspace with the stub pack."""
    workspace = tmp_path / "workspace"
    result = generate_part(
        "Build a plate", workspace, _FakeClient(GOOD), _runner(), _settings(),
        STUB_PACK, timeout_s=60, part_id=PART_ID)
    write_generate_manifest(result)
    assert result.status == "ok", result.error
    return workspace


def _edit(workspace: Path, client, instruction: str = INSTRUCTION, **overrides):
    """Run one edit of a workspace with the stub pack."""
    return edit_part(workspace, instruction, client, _runner(),
                     _settings(**overrides), STUB_PACK, timeout_s=60)


def _snapshot(folder: Path) -> dict[str, bytes]:
    """Return the bytes of every file under a folder."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*")) if path.is_file()
    }


def _manifest(folder: Path) -> dict:
    """Return the manifest of a workspace."""
    with (folder / "result.toml").open("rb") as handle:
        return tomllib.load(handle)


def _step_of(folder: Path) -> Path:
    """Return the exported STEP of a workspace."""
    return folder / _manifest(folder)["step_file"]


def test_bootstrap_copies_the_workspace_into_the_first_revision(tmp_path):
    workspace = _workspace(tmp_path)
    root_manifest = (workspace / "result.toml").read_bytes()
    root_project = _snapshot(workspace / "project")
    history = ensure_history(workspace)
    assert history.active_revision == "r0001"
    revision = workspace / "revisions" / "r0001"
    assert (revision / "result.toml").read_bytes() == root_manifest
    assert _snapshot(revision / "project") == root_project
    assert (workspace / "result.toml").read_bytes() == root_manifest
    assert _snapshot(workspace / "project") == root_project
    text = (workspace / "history.toml").read_text(encoding="utf-8")
    assert 'rel_dir = "revisions/r0001"' in text
    assert str(workspace) not in text
    assert ":" not in text


def test_a_failed_initial_workspace_is_never_editable(tmp_path):
    workspace = tmp_path / "broken"
    result = generate_part(
        "Build a plate", workspace, _FakeClient(BAD), _runner(),
        _settings(max_attempts=1), STUB_PACK, timeout_s=60, part_id=PART_ID)
    write_generate_manifest(result)
    assert result.status == "error"
    with pytest.raises(RevisionError):
        ensure_history(workspace)
    with pytest.raises(RevisionError):
        _edit(workspace, _FakeClient(GOOD))
    assert not (workspace / "history.toml").exists()
    assert not (workspace / "revisions").exists()


def test_an_unverified_manifest_is_never_editable(tmp_path):
    workspace = _workspace(tmp_path)
    (workspace / "result.toml").write_text(
        'status = "ok"\nis_valid = false\nis_single_solid = true\n'
        'part_file = "project/parts/part0001_candidate.stub"\n',
        encoding="utf-8")
    with pytest.raises(RevisionError):
        ensure_history(workspace)
    with pytest.raises(RevisionError):
        _edit(workspace, _FakeClient(GOOD))


def test_the_edit_requirement_holds_four_labelled_blocks():
    manifest = {"volume": 36000.0, "bbox_size": [120.0, 60.0, 5.0],
                "hole_count": 2, "holes": []}
    requirement = compose_edit_requirement(INSTRUCTION, "SOURCE", manifest)
    assert "Requested change:" in requirement
    assert "Current verified part" in requirement
    assert "volume: 36000.0" in requirement
    assert "bbox_size: [120.0, 60.0, 5.0]" in requirement
    assert "hole_count: 2" in requirement
    assert "Current verified source code:" in requirement
    assert "SOURCE" in requirement
    assert "Editing rules:" in requirement
    assert "ONLY the requested change" in requirement


def test_a_successful_edit_promotes_a_new_revision(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    first = _snapshot(workspace / "revisions" / "r0001")
    client = _FakeClient(GOOD)
    result = _edit(workspace, client)
    assert result.promoted is True and result.status == "ok"
    assert result.revision_id == "r0002"
    assert result.parent_revision == "r0001"
    assert result.active_revision == "r0002"
    assert (workspace / "revisions" / "r0002" / "result.toml").is_file()
    prompt = client.requests[0].prompt
    assert INSTRUCTION in prompt
    assert "volume:" in prompt and "bbox_size:" in prompt
    assert "hole_count:" in prompt and "holes:" in prompt
    assert GOOD in prompt
    assert "Editing rules:" in prompt
    assert _snapshot(workspace / "revisions" / "r0001") == first
    history = load_history(workspace)
    assert history.active_revision == "r0002"
    entry = history.revisions[-1]
    assert entry.parent == "r0001" and entry.kind == "edit"
    assert entry.status == "ok" and entry.instruction == INSTRUCTION
    names = {path.name for path in workspace.rglob("*")}
    assert not names & {"task.toml", "answer.toml", "expect"}


def test_a_failed_edit_keeps_the_active_revision(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    assert _edit(workspace, _FakeClient(GOOD)).promoted is True
    second = _snapshot(workspace / "revisions" / "r0002")
    result = _edit(workspace, _FakeClient(BAD), max_attempts=1)
    assert result.promoted is False and result.status == "error"
    assert result.revision_id == "r0003"
    assert result.parent_revision == "r0002"
    assert result.active_revision == "r0002"
    assert _manifest(workspace / "revisions" / "r0003")["status"] == "error"
    assert _snapshot(workspace / "revisions" / "r0002") == second
    assert load_history(workspace).active_revision == "r0002"


def test_a_bounded_repair_promotes_the_second_attempt(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    result = _edit(workspace, _FakeClient([BAD, GOOD]), max_attempts=2)
    assert result.promoted is True
    assert result.generate.attempts == 2
    assert load_history(workspace).revisions[-1].attempts == 2


def test_an_orphan_revision_folder_is_never_promoted(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    assert _edit(workspace, _FakeClient(GOOD)).promoted is True
    (workspace / "revisions" / "r0003").mkdir()
    history = load_history(workspace)
    assert history.active_revision == "r0002"
    assert len(history.revisions) == 2
    result = _edit(workspace, _FakeClient(GOOD))
    assert result.revision_id == "r0004"
    assert result.active_revision == "r0004"


def test_a_rollback_selects_a_verified_revision(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    assert _edit(workspace, _FakeClient(GOOD)).promoted is True
    assert _edit(workspace, _FakeClient(BAD), max_attempts=1).promoted is False
    history = rollback_revision(workspace, "r0001")
    assert history.active_revision == "r0001"
    assert load_history(workspace).active_revision == "r0001"
    assert (workspace / "revisions" / "r0002").is_dir()
    assert (workspace / "revisions" / "r0003").is_dir()
    with pytest.raises(RevisionError):
        rollback_revision(workspace, "r0003")
    with pytest.raises(RevisionError):
        rollback_revision(workspace, "r9999")


def test_a_history_with_an_escaping_path_is_refused(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    text = (workspace / "history.toml").read_text(encoding="utf-8")
    for bad in ("../escape", "C:/escape", "/escape", "revisions/../../out"):
        (workspace / "history.toml").write_text(
            text.replace('rel_dir = "revisions/r0001"', f'rel_dir = "{bad}"'),
            encoding="utf-8")
        with pytest.raises(RevisionError):
            load_history(workspace)


def test_a_history_with_an_escaping_symlink_is_refused(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        os.symlink(outside, workspace / "revisions" / "r0002",
                   target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow symbolic links")
    text = (workspace / "history.toml").read_text(encoding="utf-8")
    (workspace / "history.toml").write_text(
        text.replace('rel_dir = "revisions/r0001"',
                     'rel_dir = "revisions/r0002"'),
        encoding="utf-8")
    with pytest.raises(RevisionError):
        load_history(workspace)


def test_a_history_with_a_escaping_resolve_is_refused(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)

    def escape(root, rel):
        raise PathEscapeError(f"{rel} is outside {root}")

    monkeypatch.setattr("aturb.agent.revisions.resolve_inside", escape)
    with pytest.raises(RevisionError):
        load_history(workspace)


def test_an_empty_instruction_changes_nothing(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    before = (workspace / "history.toml").read_bytes()
    with pytest.raises(RevisionError):
        _edit(workspace, _FakeClient(GOOD), instruction="   ")
    assert (workspace / "history.toml").read_bytes() == before
    assert not (workspace / "revisions" / "r0002").exists()


def test_the_viewer_opens_a_revision_folder(tmp_path):
    workspace = _workspace(tmp_path)
    ensure_history(workspace)
    assert _edit(workspace, _FakeClient(GOOD)).promoted is True
    loaded = load_workspace(active_revision_dir(workspace))
    assert loaded.manifest["status"] == "ok"
    assert loaded.artifacts["step_file"] is not None
    rollback_revision(workspace, "r0001")
    loaded = load_workspace(active_revision_dir(workspace))
    assert loaded.manifest["status"] == "ok"
    assert loaded.artifacts["part_file"] is not None


_HEADER = '''"""Base plate. Units: millimetres."""
# --- PARAMS ---
LENGTH_MM = 100.0
WIDTH_MM = 50.0
THICKNESS_MM = 8.0
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

'''
_PLATE = '''    body = doc.addObject("PartDesign::Body", "Body")
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
'''
_BOSS = '''    boss_sketch = body.newObject("Sketcher::SketchObject", "BossSketch")
    boss_sketch.Placement = App.Placement(
        App.Vector(0, 0, THICKNESS_MM), App.Rotation())
    boss_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), 10.0), False)
    boss = body.newObject("PartDesign::Pad", "Boss")
    boss.Profile = boss_sketch
    boss.Length = 10.0
'''
PLATE = _HEADER + _PLATE + "    return body\n"
BOSS = (_HEADER.replace("THICKNESS_MM = 8.0", "THICKNESS_MM = 12.0")
        + _PLATE + _BOSS + "    return body\n")
BROKEN = "def build(doc):\n    return (\n"


@pytest.mark.freecad
def test_a_real_edit_promotes_a_measured_revision_and_rolls_back(tmp_path):
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())
    workspace = tmp_path / "workspace"
    result = generate_part(
        "Build a base plate", workspace, _FakeClient(
            PLATE), runner, _settings(),
        FREECAD_PACK, timeout_s=timeout_s(cfg), part_id=PART_ID)
    write_generate_manifest(result)
    assert result.status == "ok", result.error
    ensure_history(workspace)
    edit = edit_part(
        workspace, "Make it 12 mm thick and add a boss", _FakeClient(BOSS),
        runner, _settings(), FREECAD_PACK, timeout_s=timeout_s(cfg))
    assert edit.promoted is True, edit.error
    assert edit.active_revision == "r0002"
    model = load_step(_step_of(active_revision_dir(workspace)))
    assert model.is_valid and model.is_single_solid
    assert model.volume == pytest.approx(63141.592654, abs=0.05)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx((100.0, 50.0, 22.0))
    step_path = _step_of(active_revision_dir(workspace))
    before = step_path.read_bytes()
    failed = edit_part(
        workspace, "Break it", _FakeClient(BROKEN), runner,
        _settings(max_attempts=1), FREECAD_PACK, timeout_s=timeout_s(cfg))
    assert failed.promoted is False
    assert failed.active_revision == "r0002"
    assert step_path.read_bytes() == before
    rollback_revision(workspace, "r0001")
    assert load_history(workspace).active_revision == "r0001"
    model = load_step(_step_of(active_revision_dir(workspace)))
    assert model.volume == pytest.approx(40000.0, abs=0.05)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx((100.0, 50.0, 8.0))
