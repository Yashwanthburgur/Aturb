"""Tests for the assembly edit tasks of the evaluation set.

The offline half checks the shape of the task folders: every task names its
assembly, holds the project, the instruction and the expected values. The
real half builds the tasks with the real backend pack and measures the
edited assembly; it is marked freecad and never runs in CI.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

from aturb.agent.types import ModelRequest, ModelResponse
from aturb.assembly.agent import edit_assembly
from aturb.assembly.manifest import load_assembly
from aturb.config import load_config
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = REPO_ROOT / "evals" / "assemblies"
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
TASK_IDS = ("pin_in_plate_upsize", "bushing_in_housing")
VOLUME_TOL = 0.5  # starting default
CLEARANCE_TOL = 0.02  # starting default
SIZE_TOL = 0.01  # starting default
BUILD_TIMEOUT_S = 180  # starting default

CAD_TERMS = ("freecad", "solidworks", "onshape", "catia", "fusion")

UPSIZES = {
    "pin_in_plate_upsize": {
        "plt0001": {"BORE_DIAMETER_MM = 20.4": "BORE_DIAMETER_MM = 24.4"},
        "shf0001": {"SHAFT_DIAMETER_MM = 20.0": "SHAFT_DIAMETER_MM = 24.0"},
    },
    "bushing_in_housing": {
        "hsg0001": {"BORE_DIAMETER_MM = 30.4": "BORE_DIAMETER_MM = 34.4"},
        "bsh0001": {
            "BARREL_DIAMETER_MM = 30.0": "BARREL_DIAMETER_MM = 34.0",
            "FLANGE_DIAMETER_MM = 44.0": "FLANGE_DIAMETER_MM = 48.0",
        },
    },
}

INNER_PART = {"pin_in_plate_upsize": "shf0001",
              "bushing_in_housing": "bsh0001"}


class FakeClient:
    """A model client that answers with canned texts and records the prompts."""

    def __init__(self, answers: list[str]) -> None:
        """Take the answers, one per call."""
        self.answers = list(answers)
        self.prompts: list[str] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the next canned text and record the prompt."""
        self.prompts.append(request.prompt)
        text = self.answers.pop(0) if self.answers else ""
        return ModelResponse(text=text, input_tokens=10, output_tokens=20)


def _task(task_id: str) -> Path:
    """Return the folder of one task of the set."""
    return TASKS_DIR / task_id


def _read_toml(path: Path) -> dict:
    """Read one TOML file of a task."""
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _metadata(task_id: str) -> dict:
    """Return the metadata of one task of the set."""
    return _read_toml(_task(task_id) / "assembly_task.toml")


def _manifest_path(project: Path, task_id: str) -> Path:
    """Return the manifest of the assembly inside a copied project."""
    return project / _metadata(task_id)["assembly_file"]


def _instruction(task_id: str) -> str:
    """Return the instruction of one task of the set."""
    data = _metadata(task_id)
    path = _task(task_id) / data["project_dir"] / data["requirement_file"]
    return path.read_text(encoding="utf-8")


def _source(project: Path, part_id: str) -> str:
    """Return the source of one part of a project."""
    matches = sorted(project.glob(f"parts/{part_id}_*"))
    assert len(matches) == 1, matches
    return matches[0].read_text(encoding="utf-8")


def _block(part_id: str, source: str) -> str:
    """Return one answer that updates one part."""
    return (f"# === PART: {part_id} ===\n{source.rstrip()}\n"
            f"# === END PART: {part_id} ===\n")


def _answer(project: Path, task_id: str, part_ids: list[str]) -> str:
    """Return the answer that upsizes the given parts of a task."""
    blocks = []
    for part_id in part_ids:
        source = _source(project, part_id)
        for old, new in UPSIZES[task_id][part_id].items():
            source = source.replace(old, new)
        blocks.append(_block(part_id, source))
    return "".join(blocks)


def _copy_task(tmp_path: Path, task_id: str) -> Path:
    """Copy the project of one task into a scratch folder."""
    data = _metadata(task_id)
    project = tmp_path / "project"
    shutil.copytree(_task(task_id) / data["project_dir"], project)
    return project


def _runner():
    """Return the runner of the real backend pack."""
    if not LOCAL_CONFIG.is_file():
        pytest.skip("the local FreeCAD configuration is not on this machine")
    cfg = load_config(LOCAL_CONFIG)
    return load_runner("freecad", cfg, default_packs_root())


def _settings() -> dict:
    """Return the agent settings of a test."""
    return {"model": "test-model", "max_attempts": 3}


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_every_task_holds_its_files(task_id):
    """A task holds its metadata, its project and its expected values."""
    task = _task(task_id)
    data = _metadata(task_id)

    assert (task / "assembly_task.toml").is_file()
    assert (task / "expected_edit.toml").is_file()
    project = task / data["project_dir"]
    assert (project / data["assembly_file"]).is_file()
    assert (project / data["requirement_file"]).is_file()
    assert (project / "parts").is_dir()


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_task_names_its_own_assembly(task_id):
    """The task, the manifest and the expected values name one assembly."""
    task = _task(task_id)
    data = _metadata(task_id)
    expected = _read_toml(task / "expected_edit.toml")
    manifest = _read_toml(task / data["project_dir"] / data["assembly_file"])

    assert data["task_id"] == task_id
    assert data["assembly_id"] == expected["assembly_id"]
    assert manifest["assembly_id"] == data["assembly_id"]
    assert len(manifest["components"]) == 2
    assert manifest["mates"]


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_manifest_of_the_task_loads(task_id):
    """The manifest of the task is a manifest the core accepts."""
    data = _metadata(task_id)
    path = _task(task_id) / data["project_dir"] / data["assembly_file"]

    spec = load_assembly(path)

    assert spec.assembly_id == data["assembly_id"]
    assert len(spec.components) == 2
    assert spec.mates


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_expected_values_are_usable(task_id):
    """The expected values hold a volume, a box, a clearance and a verdict."""
    expected = _read_toml(_task(task_id) / "expected_edit.toml")

    assert expected["total_volume_mm3"] > 0.0
    assert len(expected["bbox_size_mm"]) == 3
    assert all(size > 0.0 for size in expected["bbox_size_mm"])
    assert expected["min_clearance_mm"] > 0.0
    assert expected["has_interference"] is False
    assert expected["updated_parts"]


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_instruction_names_the_change_to_make(task_id):
    """The instruction of the task names the dimensions to change."""
    text = _instruction(task_id)

    assert "mm" in text
    assert "clearance" in text
    for changes in UPSIZES[task_id].values():
        for new in changes.values():
            assert new.split("=")[1].strip() in text


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_task_metadata_names_no_cad_system(task_id):
    """The metadata of a task is CAD-neutral: it names no CAD system."""
    task = _task(task_id)
    data = _metadata(task_id)
    project = task / data["project_dir"]
    files = [
        task / "assembly_task.toml",
        task / "expected_edit.toml",
        project / data["assembly_file"],
        project / data["requirement_file"],
    ]

    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for term in CAD_TERMS:
            assert term not in text, f"{path.name} names {term}"


@pytest.mark.freecad
@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_golden_coupled_edit_measures_the_expected_assembly(tmp_path, task_id):
    """The coupled edit of the task verifies and shows the expected numbers."""
    project = _copy_task(tmp_path, task_id)
    expected = _read_toml(_task(task_id) / "expected_edit.toml")
    client = FakeClient([_answer(project, task_id, list(UPSIZES[task_id]))])

    result = edit_assembly(
        project, _manifest_path(project, task_id), _instruction(task_id),
        client=client, runner=_runner(), settings=_settings(),
        timeout_s=BUILD_TIMEOUT_S, record_revision=True)

    assert result.status == "ok", result.error
    assert result.promoted is True
    assert result.stop_reason == "built"
    assert result.attempts == 1
    assert set(result.updated_parts) == set(expected["updated_parts"])
    report = result.build.report if result.build else None
    assert report is not None
    assert not report.has_interference
    assert abs(report.total_volume -
               expected["total_volume_mm3"]) <= VOLUME_TOL
    for measured, wanted in zip(
            report.bbox_size, expected["bbox_size_mm"], strict=True):
        assert abs(measured - wanted) <= SIZE_TOL
    pair = report.pairs[0]
    assert abs(pair.min_clearance_mm -
               expected["min_clearance_mm"]) <= CLEARANCE_TOL
    assert pair.overlap_volume_mm3 <= 1e-3


@pytest.mark.freecad
@pytest.mark.parametrize("task_id", TASK_IDS)
def test_a_clashing_first_answer_is_repaired_on_the_next_attempt(tmp_path, task_id):
    """An answer that clashes is refused, and the next one is promoted."""
    project = _copy_task(tmp_path, task_id)
    inner = INNER_PART[task_id]
    client = FakeClient([
        _answer(project, task_id, [inner]),
        _answer(project, task_id, list(UPSIZES[task_id])),
    ])

    result = edit_assembly(
        project, _manifest_path(project, task_id), _instruction(task_id),
        client=client, runner=_runner(), settings=_settings(),
        timeout_s=BUILD_TIMEOUT_S, record_revision=True)

    assert result.status == "ok", result.error
    assert result.promoted is True
    assert result.attempts == 2
    assert len(client.prompts) == 2
    assert "Assembly Repair" in client.prompts[1]
