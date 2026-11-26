"""The multi-feature evaluation tasks: loaded offline and judged in the real CAD.

The six tasks of this file are the multi-feature mechanical parts of the
repository. The offline tests prove that every task loads, that every prompt
is CAD-neutral and that every expected value is usable. The FreeCAD tests
build the golden reference part of every task through the production runner
and judge it with ``judge_task()``.

The task loader of the core is ``aturb.evals.task.load_task()`` and the answer
loader is ``aturb.evals.answer.load_answer()``; there is no
``aturb.evals.loader`` module.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.evals.answer import load_answer
from aturb.evals.judge import judge_task
from aturb.evals.result import OK
from aturb.evals.task import load_task
from aturb.packs import default_packs_root, load_runner
from aturb.verify.expectations import checks_from_expectations, load_expectations
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_ROOT = REPO_ROOT / "evals" / "tasks"
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"

VOLUME_TOLERANCE_MM3 = 0.05  # starting default
SIZE_TOLERANCE_MM = 1e-6  # starting default
BUILD_TIMEOUT_S = 180  # starting default

TASK_IDS = (
    "bossed_plate_pocket",
    "enclosure_housing",
    "flanged_hub_counterbore",
    "l_bracket_chamfer",
    "ribbed_l_bracket",
    "stepped_shaft",
)

PART_IDS = {
    "bossed_plate_pocket": "plt0005",
    "enclosure_housing": "enc0001",
    "flanged_hub_counterbore": "hub0001",
    "l_bracket_chamfer": "brk0001",
    "ribbed_l_bracket": "brk0002",
    "stepped_shaft": "shf0001",
}

EXPECTED_VOLUMES = {
    "bossed_plate_pocket": 50257.875778608266,
    "enclosure_housing": 99737.68116783851,
    "flanged_hub_counterbore": 67261.49871335747,
    "l_bracket_chamfer": 47467.61065788307,
    "ribbed_l_bracket": 51147.61065788307,
    "stepped_shaft": 20169.02483604647,
}

EXPECTED_BBOXES = {
    "bossed_plate_pocket": (100.0, 60.0, 20.0),
    "enclosure_housing": (100.0, 70.0, 30.0),
    "flanged_hub_counterbore": (80.0, 80.0, 30.0),
    "l_bracket_chamfer": (80.0, 50.0, 48.0),
    "ribbed_l_bracket": (80.0, 50.0, 48.0),
    "stepped_shaft": (30.0, 30.0, 50.0),
}

EXPECTED_HOLE_COUNTS = {
    "bossed_plate_pocket": 1,
    "enclosure_housing": 4,
    "flanged_hub_counterbore": 6,
    "l_bracket_chamfer": 2,
    "ribbed_l_bracket": 2,
    "stepped_shaft": 0,
}

# The expectation schema holds one expected diameter for every hole, so the
# 14 mm bore and the 24 mm counterbore of the flanged hub cannot be named
# separately. The two checks that would compare those diameters against the
# single expected value are the only checks that cannot pass, and the answer
# file does not require them. Every other check of every task must pass.
UNREPRESENTABLE_CHECKS = {
    "flanged_hub_counterbore": frozenset({"hole_2_diameter", "hole_3_diameter"}),
}

BRAND_PATTERN = re.compile(
    r"\b(freecad|fcstd|partdesign|sketcher|solidworks|onshape|fusion|"
    r"featurescript|catia|inventor|solid\s+edge|siemens\s+nx|creo|rhino|"
    r"blender|openscad)\b",
    re.IGNORECASE,
)

BASE_CHECKS = frozenset({"volume", "bbox_x", "bbox_y", "bbox_z", "hole_count"})
HOLE_CHECK = re.compile(r"hole_\d+_(?:diameter|x|y)")


def _task_dir(task_id: str) -> Path:
    """Return the folder of one task."""
    return TASKS_ROOT / task_id


def _copy_task(tmp_path: Path, task_id: str) -> Path:
    """Copy one task folder into the temporary folder, without its build output."""
    target = tmp_path / task_id
    shutil.copytree(_task_dir(task_id), target,
                    ignore=shutil.ignore_patterns("out"))
    return target


def _runner():
    """Return the production runner of the real CAD, or skip the test."""
    if not LOCAL_CONFIG.is_file():
        pytest.skip("the local FreeCAD configuration is not on this machine")
    cfg = load_config(LOCAL_CONFIG)
    return load_runner("freecad", cfg, default_packs_root())


def test_the_six_task_folders_are_discovered():
    """Every new task is an immediate subfolder of the task root."""
    folders = {path.name for path in TASKS_ROOT.iterdir() if path.is_dir()}
    for task_id in TASK_IDS:
        assert task_id in folders


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_every_task_loads(task_id):
    """The task file and the answer file of every task load and agree."""
    folder = _task_dir(task_id)
    task = load_task(folder)
    answer = load_answer(folder)
    assert task.task_id == task_id
    assert task.part_id == PART_IDS[task_id]
    assert answer.task_id == task.task_id
    assert answer.part_id == task.part_id
    assert answer.max_score == 1.0
    assert answer.required_checks


def test_the_part_ids_of_the_new_tasks_are_unique():
    """No two new tasks build the same part."""
    part_ids = [PART_IDS[task_id] for task_id in TASK_IDS]
    assert len(set(part_ids)) == len(part_ids)


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_no_prompt_names_a_cad_brand(task_id):
    """Neither the task file nor the answer file names a CAD brand."""
    folder = _task_dir(task_id)
    for name in ("task.toml", "answer.toml"):
        text = (folder / name).read_text(encoding="utf-8")
        found = BRAND_PATTERN.search(text)
        assert found is None, f"{name} names a CAD brand: {found.group(0)!r}"


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_expected_values_are_usable(task_id):
    """The expectation file holds positive numbers that agree with each other."""
    folder = _task_dir(task_id)
    answer = load_answer(folder)
    expected = load_expectations(folder / "project" / answer.expect_file)
    assert expected["volume"] > 0.0
    assert all(size > 0.0 for size in expected["bbox"])
    assert expected["hole_count"] >= 0
    assert len(expected["hole_positions"]) == expected["hole_count"]


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_every_required_check_is_a_known_name(task_id):
    """Every required check is a base check or a per-hole check."""
    answer = load_answer(_task_dir(task_id))
    for name in answer.required_checks:
        assert name in BASE_CHECKS or HOLE_CHECK.fullmatch(name), name


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_every_task_holds_a_golden_part_and_a_requirement(task_id):
    """The task folder holds the part, the requirement and the expectation."""
    folder = _task_dir(task_id)
    part_id = PART_IDS[task_id]
    project = folder / "project"
    assert list((project / "parts").glob(f"{part_id}_*.py"))
    assert list((project / "parts").glob(f"{part_id}_*.stub"))
    assert (project / "requirements" / f"{part_id}.md").is_file()
    assert (project / "expect" / f"{part_id}.toml").is_file()


@pytest.mark.freecad
@pytest.mark.parametrize("task_id", TASK_IDS)
def test_the_golden_part_passes_every_required_check(tmp_path, task_id):
    """The golden reference part of every task is judged ok, with no failed check."""
    folder = _copy_task(tmp_path, task_id)
    answer = load_answer(folder)
    judgement = judge_task(folder, _runner(), BUILD_TIMEOUT_S)

    assert judgement.build_status == "ok", judgement.error_text
    assert judgement.error_text == ""
    assert judgement.result.status == OK, judgement.result.error
    assert judgement.result.score == 1.0
    assert judgement.result.error == ""

    geometry = judgement.geometry
    assert geometry is not None
    assert geometry.is_valid
    assert geometry.is_single_solid
    assert geometry.volume == pytest.approx(
        EXPECTED_VOLUMES[task_id], abs=VOLUME_TOLERANCE_MM3)
    assert geometry.bbox_size == pytest.approx(
        EXPECTED_BBOXES[task_id], abs=SIZE_TOLERANCE_MM)
    assert len(geometry.holes) == EXPECTED_HOLE_COUNTS[task_id]

    steps = sorted(folder.glob("project/out/**/*.step"))
    assert len(steps) == 1
    model = load_step(steps[0])
    expected = load_expectations(folder / "project" / answer.expect_file)
    checks = checks_from_expectations(model, expected)
    by_name = {check.name: check for check in checks}
    for name in answer.required_checks:
        assert name in by_name, f"{task_id}: the check {name} was not produced"
        assert by_name[name].passed, f"{task_id}: the check {name} did not pass"
    failed = {check.name for check in checks if not check.passed}
    assert failed == UNREPRESENTABLE_CHECKS.get(task_id, frozenset())
