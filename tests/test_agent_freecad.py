"""FreeCAD tests: the agent path with the real CAD.

The same path as the stub test, but with the FreeCAD pack: the agent writes a
candidate, the pack builds it in the CAD, the neutral checks run over the
exported STEP and the task is scored. The local configuration is used the way
the demo plate test uses it.

The fillet task is the one that needs the helper of the pack: its candidate
selects the edges of the fillet by their geometry, the pack builds it and the
neutral checks judge the exported STEP.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.run import run_agent
from aturb.agent.types import ModelRequest, ModelResponse
from aturb.config import load_config, timeout_s
from aturb.evals.runner import run_task
from aturb.packs import default_packs_root, load_manifest, load_runner
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
FILLET_TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_fillet"
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
FREECAD_PACK = load_manifest(REPO_ROOT / "packs" / "freecad" / "pack.toml")

TASK_ID = "plate_2holes"
FILLET_TASK_ID = "plate_fillet"
FILLET_PART_ID = "plt0002"
MODEL = "some-model-id"

# The canned answer of the fake client: the committed part file of the task.
# The client plays the model here; the agent itself never reads this file.
CANDIDATE = (
    TASK_DIR / "project" / "parts" / "plt0001_base_plate.py"
).read_text(encoding="utf-8")

# The canned answer for the fillet task: the committed reference part, which
# selects the edges of the fillet with the helper of the pack.
FILLET_CANDIDATE = (
    FILLET_TASK_DIR / "project" / "parts" / "plt0002_base_plate_fillet.py"
).read_text(encoding="utf-8")

# A candidate the pack refuses: its static safety check bans the import.
REFUSED = "import os\n\n\ndef build(doc):\n    return None\n"


class _FakeClient:
    """A model client that answers with a canned candidate."""

    def __init__(self, text: str) -> None:
        """Take the candidate the client returns."""
        self.text = text
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Record the request and return the canned candidate."""
        self.requests.append(request)
        return ModelResponse(text=self.text, input_tokens=120, output_tokens=45)


def make_runner():
    """Load the production FreeCAD runner with the local config."""
    cfg = load_config(LOCAL_CONFIG)
    return load_runner("freecad", cfg, default_packs_root())


def make_settings():
    """Return the agent settings of the tests."""
    return agent_settings({"agent": {"model": MODEL}})


def _files(folder: Path) -> set[str]:
    """Return the relative paths of every file under a folder."""
    return {
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file()
    }


def _expected_volume(task_dir: Path, part_id: str) -> float:
    """Return the expected volume of a part, read from its expectation file."""
    path = task_dir / "project" / "expect" / f"{part_id}.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)["volume"]


@pytest.mark.freecad
def test_the_agent_path_scores_the_task_with_freecad(tmp_path):
    """The agent writes a candidate, FreeCAD builds it and the task scores 1.0."""
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())
    client = _FakeClient(CANDIDATE)

    run = run_agent(TASK_DIR, client, make_settings(), FREECAD_PACK, tmp_path)

    assert run.status == "ok"
    assert len(client.requests) == 1
    scratch = tmp_path / TASK_ID
    candidate = scratch / "project" / "parts" / "plt0001_candidate.py"
    assert candidate.is_file()
    result = run_task(scratch, runner, timeout_s(cfg))
    assert result.status == "ok", result.error
    assert result.score == 1.0


@pytest.mark.freecad
def test_a_refused_candidate_gives_an_error_result(tmp_path):
    """A candidate the pack refuses gives an error result that says why."""
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())
    client = _FakeClient(REFUSED)

    run = run_agent(TASK_DIR, client, make_settings(), FREECAD_PACK, tmp_path)

    assert run.status == "ok"
    result = run_task(tmp_path / TASK_ID, runner, timeout_s(cfg))
    assert result.status == "error"
    assert "not allowed" in result.error


@pytest.mark.freecad
def test_the_agent_path_scores_the_fillet_task_with_freecad(tmp_path):
    """The candidate selects the fillet edges with the helper and scores 1.0."""
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())
    client = _FakeClient(FILLET_CANDIDATE)
    before = _files(FILLET_TASK_DIR)

    run = run_agent(FILLET_TASK_DIR, client,
                    make_settings(), FREECAD_PACK, tmp_path)

    assert run.status == "ok"
    scratch = tmp_path / FILLET_TASK_ID
    candidate = scratch / "project" / "parts" / \
        f"{FILLET_PART_ID}_candidate.py"
    assert candidate.is_file()
    assert "helper.corner_edges" in candidate.read_text(encoding="utf-8")

    result = run_task(scratch, runner, timeout_s(cfg))
    assert result.status == "ok", result.error
    assert result.score == 1.0

    # The neutral checks ran over the exported STEP of the scratch project.
    steps = list((scratch / "project" / "out").rglob("*.step"))
    assert len(steps) == 1
    model = load_step(steps[0])
    assert model.is_single_solid
    expected = _expected_volume(FILLET_TASK_DIR, FILLET_PART_ID)
    assert abs(model.volume - expected) <= 0.01
    # The four fillets add four round faces to the eight faces of the plate.
    assert len(model.faces) == 12

    # The committed task is never written to.
    assert _files(FILLET_TASK_DIR) == before
