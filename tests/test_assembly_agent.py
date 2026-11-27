"""Offline tests for the assembly prompt, the parser and the bounded loop.

The stub pack builds every part by copying a packaged fixture STEP, so the
whole pipeline runs without a CAD, and the model is a fake client.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.agent.types import AgentError, ModelRequest, ModelResponse
from aturb.assembly.agent import edit_assembly
from aturb.assembly.build import build_assembly
from aturb.assembly.manifest import load_assembly
from aturb.assembly.prompt import (
    AssemblyParseError,
    compose_assembly_edit_prompt,
    parse_part_updates,
)
from aturb.packs import default_packs_root, load_runner

PART_TEXT = ("# --- PARAMS ---\nPLATE_LENGTH_MM = 120.0\n"
             "PLATE_WIDTH_MM = 60.0\n# --- END PARAMS ---\n")
BROKEN_TEXT = "# STUB: fail=syntax_error\n"
UPDATED_TEXT = "# updated part\n"
INSTRUCTION = "raise the top plate by 1 mm"

MANIFEST = """
assembly_id = "asm0001"
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
max_clearance_mm = 1.5
"""


class FakeClient:
    """A model client that answers with canned texts and records the prompts."""

    def __init__(self, answers: list[str], error: str = "") -> None:
        """Take the answers, one per call, and an optional failure."""
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.error = error

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the next canned text and record the prompt."""
        self.prompts.append(request.prompt)
        if self.error:
            raise AgentError(self.error)
        text = self.answers.pop(0) if self.answers else ""
        return ModelResponse(text=text, input_tokens=10, output_tokens=20)


def _runner():
    """Load the stub runner with empty settings."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def _project(tmp_path: Path) -> Path:
    """Write a project with two stub parts and one assembly manifest."""
    project = tmp_path / "project"
    (project / "parts").mkdir(parents=True)
    (project / "parts" / "plt0001_base_plate.stub").write_text(
        PART_TEXT, encoding="utf-8")
    (project / "parts" / "plt0002_top_plate.stub").write_text(
        PART_TEXT, encoding="utf-8")
    (project / "assemblies").mkdir(parents=True)
    (project / "assemblies" / "asm0001.toml").write_text(
        MANIFEST, encoding="utf-8")
    return project


def _manifest_path(project: Path) -> Path:
    """Return the manifest of the assembly of a project."""
    return project / "assemblies" / "asm0001.toml"


def _block(part_id: str, source: str) -> str:
    """Return one answer that updates one part."""
    return (f"# === PART: {part_id} ===\n{source}"
            f"# === END PART: {part_id} ===\n")


def _settings(**overrides) -> dict:
    """Return the agent settings of a test, with the overrides applied."""
    settings = {"model": "test-model", "max_attempts": 3}
    settings.update(overrides)
    return settings


def _edit(project: Path, client, instruction: str = INSTRUCTION, **overrides):
    """Run one assembly edit over a project with the given client."""
    return edit_assembly(
        project, _manifest_path(project), instruction, client=client,
        runner=_runner(), settings=_settings(**overrides))


def _snapshot(root: Path) -> dict[str, bytes]:
    """Return the bytes of every file of a folder, keyed by its relative path."""
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


def test_a_single_part_block_is_parsed():
    """One block gives the new source of one part."""
    updates = parse_part_updates(_block("plt0001", "code one\n"),
                                 ("plt0001", "plt0002"))

    assert updates == {"plt0001": "code one\n"}


def test_several_part_blocks_are_parsed():
    """Two blocks give the new source of two parts."""
    text = _block("plt0001", "code one\n") + _block("plt0002", "code two\n")

    updates = parse_part_updates(text, ("plt0001", "plt0002"))

    assert updates == {"plt0001": "code one\n", "plt0002": "code two\n"}


def test_a_fenced_answer_is_unwrapped():
    """An outer fence and an inner fence are both removed."""
    text = ("```\n# === PART: plt0001 ===\n```python\ncode one\n```\n"
            "# === END PART: plt0001 ===\n```\n")

    updates = parse_part_updates(text, ("plt0001",))

    assert updates == {"plt0001": "code one\n"}


@pytest.mark.parametrize("text", [
    _block("plt0009", "x\n"),
    _block("plt0001", "x\n") + _block("plt0001", "y\n"),
    "# === PART: plt0001 ===\nx\n",
    "# === PART: plt0001 ===\nx\n# === END PART: plt0002 ===\n",
    _block("plt0001", "   \n"),
    "here is the new source of the plate\n",
], ids=["unknown", "duplicate", "unclosed", "mismatched", "empty", "no-block"])
def test_a_broken_answer_is_refused(text):
    """Every broken answer is refused by the strict parser."""
    with pytest.raises(AssemblyParseError):
        parse_part_updates(text, ("plt0001", "plt0002"))


def test_the_prompt_carries_the_assembly_context(tmp_path):
    """The prompt holds the parts, the mates, the measures and the contract."""
    project = _project(tmp_path)
    spec = load_assembly(_manifest_path(project))
    built = build_assembly(project, _manifest_path(project), _runner())
    assert built.status == "ok", built.error

    prompt = compose_assembly_edit_prompt(
        spec, instruction=INSTRUCTION, pack_prompt="PACK PROMPT",
        part_sources={"plt0001": PART_TEXT, "plt0002": PART_TEXT},
        report=built.report)

    assert "# --- PARAMS ---" in prompt
    assert "PLATE_LENGTH_MM = 120.0" in prompt
    assert "position=[0.0, 0.0, 6.0]" in prompt
    assert "clearance [0.5, 1.5] mm" in prompt
    assert "Current verified assembly measurements:" in prompt
    assert "total_volume" in prompt
    assert INSTRUCTION in prompt
    assert "PACK PROMPT" in prompt
    assert prompt.count("Output contract:") == 1


def test_the_prompt_of_a_repair_carries_the_feedback(tmp_path):
    """The feedback of the attempt before is the last section of the prompt."""
    project = _project(tmp_path)
    spec = load_assembly(_manifest_path(project))

    prompt = compose_assembly_edit_prompt(
        spec, instruction=INSTRUCTION, pack_prompt="",
        part_sources={"plt0001": PART_TEXT, "plt0002": PART_TEXT},
        report=None, feedback="## Assembly Repair\nfix the plate")

    assert "## Assembly Repair" in prompt
    assert prompt.count("Output contract:") == 1


def test_a_clean_answer_is_promoted(tmp_path):
    """One answer that verifies is written into the live project."""
    project = _project(tmp_path)
    client = FakeClient([_block("plt0002", UPDATED_TEXT)])

    result = _edit(project, client)

    assert result.status == "ok"
    assert result.stop_reason == "built"
    assert result.promoted is True
    assert result.attempts == 1
    assert result.updated_parts == ("plt0002",)
    assert result.build is not None and result.build.status == "ok"
    part = project / "parts" / "plt0002_top_plate.stub"
    assert part.read_text(encoding="utf-8") == UPDATED_TEXT


def test_a_format_error_is_repaired_on_the_next_attempt(tmp_path):
    """An answer without a block is repaired by the next attempt."""
    project = _project(tmp_path)
    client = FakeClient(["no markers here", _block("plt0002", UPDATED_TEXT)])

    result = _edit(project, client)

    assert result.status == "ok"
    assert result.promoted is True
    assert result.attempts == 2
    assert "Format error" in client.prompts[1]


def test_a_failing_part_is_repaired_on_the_next_attempt(tmp_path):
    """A part that fails to build is repaired by the next attempt."""
    project = _project(tmp_path)
    client = FakeClient([
        _block("plt0002", BROKEN_TEXT),
        _block("plt0002", UPDATED_TEXT),
    ])

    result = _edit(project, client)

    assert result.status == "ok"
    assert result.promoted is True
    assert result.attempts == 2
    assert "Failing part builds" in client.prompts[1]
    assert "syntax_error" in client.prompts[1]


def test_a_passed_budget_stops_the_loop(tmp_path):
    """A prompt that is over the input cap never reaches the model."""
    project = _project(tmp_path)
    client = FakeClient([_block("plt0002", UPDATED_TEXT)])

    result = _edit(project, client, max_input_tokens=1)

    assert result.status == "failed"
    assert result.stop_reason == "budget_exceeded"
    assert result.promoted is False
    assert result.attempts == 0
    assert client.prompts == []


def test_a_model_failure_stops_the_loop(tmp_path):
    """A failed model call stops the loop with its own reason."""
    project = _project(tmp_path)

    result = _edit(project, FakeClient([], error="the model call failed"))

    assert result.status == "failed"
    assert result.stop_reason == "model_error"
    assert result.promoted is False
    assert result.attempts == 1


def test_an_exhausted_loop_leaves_the_project_untouched(tmp_path):
    """A rejected edit leaves every file of the live project as it was."""
    project = _project(tmp_path)
    built = build_assembly(project, _manifest_path(project), _runner())
    assert built.status == "ok", built.error
    before = _snapshot(project)
    client = FakeClient([_block("plt0002", BROKEN_TEXT)])

    result = _edit(project, client, max_attempts=1)

    assert result.status == "failed"
    assert result.stop_reason == "max_attempts"
    assert result.promoted is False
    assert result.attempts == 1
    assert _snapshot(project) == before


def test_an_empty_instruction_is_refused(tmp_path):
    """An empty instruction never reaches the model."""
    project = _project(tmp_path)
    client = FakeClient([_block("plt0002", UPDATED_TEXT)])

    result = _edit(project, client, instruction="   ")

    assert result.status == "failed"
    assert result.stop_reason == "preparation_error"
    assert client.prompts == []
