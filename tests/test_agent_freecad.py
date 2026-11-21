"""FreeCAD tests: the agent path with the real CAD.

The same path as the stub test, but with the FreeCAD pack: the agent writes a
candidate, the pack builds it in the CAD, the neutral checks run over the
exported STEP and the task is scored. The local configuration is used the way
the demo plate test uses it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.agent.config import agent_settings
from aturb.agent.run import run_agent
from aturb.agent.types import ModelRequest, ModelResponse
from aturb.config import load_config, timeout_s
from aturb.evals.runner import run_task
from aturb.packs import default_packs_root, load_manifest, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "evals" / "tasks" / "plate_2holes"
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
FREECAD_PACK = load_manifest(REPO_ROOT / "packs" / "freecad" / "pack.toml")

TASK_ID = "plate_2holes"
MODEL = "some-model-id"

# The canned answer of the fake client: the committed part file of the task.
# The client plays the model here; the agent itself never reads this file.
CANDIDATE = (
    TASK_DIR / "project" / "parts" / "plt0001_base_plate.py"
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
