"""Tests for the prompt of one agent run.

The prompt is built in a fixed order, so the same inputs always give the same
prompt, and the version of a prompt is the hash of the exact text that is
sent. The fence of a model answer is removed and nothing else.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from aturb.agent import prompt as prompt_module
from aturb.agent.conventions import conventions_text
from aturb.agent.prompt import (
    CORE_INSTRUCTION,
    OUTPUT_CONTRACT,
    compose_prompt,
    prompt_version,
    strip_code_fence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

HEX = re.compile(r"^[0-9a-f]{16}$")

PACK_PROMPT = "Write the part in the language of this pack."
REQUIREMENT = "Build a 120 x 60 x 5 mm plate with two 10 mm through holes."


def test_the_sections_keep_their_order():
    """The five sections appear in the order the prompt is built in."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    expected = "\n\n".join([
        CORE_INSTRUCTION.strip(),
        PACK_PROMPT,
        conventions_text().strip(),
        REQUIREMENT,
        OUTPUT_CONTRACT.strip(),
    ])

    assert prompt == expected


def test_the_sections_are_separated_by_one_blank_line():
    """The five sections are joined with exactly one blank line."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    sections = prompt.split("\n\n")

    assert len(sections) == 5
    assert "\n\n\n" not in prompt


def test_the_core_instruction_asks_for_one_part_file():
    """The core instruction asks for one part file and nothing else."""
    assert "part file" in CORE_INSTRUCTION
    assert "nothing else" in CORE_INSTRUCTION


def test_the_core_instruction_names_no_task():
    """The core instruction is fixed and names no task of the set."""
    assert "plate_2holes" not in CORE_INSTRUCTION
    assert "plt0001" not in CORE_INSTRUCTION


def test_an_empty_pack_prompt_is_refused():
    """A prompt without the instructions of the pack is refused."""
    with pytest.raises(ValueError):
        compose_prompt("", REQUIREMENT)


def test_an_empty_requirement_is_refused():
    """A prompt without the intent of the task is refused."""
    with pytest.raises(ValueError):
        compose_prompt(PACK_PROMPT, "")


def test_the_version_is_sixteen_hex_characters():
    """The version is sixteen hexadecimal characters."""
    version = prompt_version("some prompt text")

    assert len(version) == 16
    assert HEX.match(version)


def test_the_version_is_the_prefix_of_the_hash():
    """The version is the first sixteen characters of the SHA-256."""
    text = "some prompt text"

    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    assert prompt_version(text) == expected


def test_the_version_changes_when_the_text_changes():
    """A different text gives a different version."""
    assert prompt_version("one prompt") != prompt_version("another prompt")


def test_the_version_is_the_same_for_the_same_text():
    """The same text always gives the same version."""
    assert prompt_version("one prompt") == prompt_version("one prompt")


def test_a_fenced_text_loses_its_fences():
    """The two fence lines are removed and the code inside is kept."""
    text = "```\nprint('hi')\n```"

    assert strip_code_fence(text) == "print('hi')\n"


def test_a_language_labelled_fence_is_removed():
    """An opening fence that names a language is removed as well."""
    text = "```python\nprint('hi')\n```"

    assert strip_code_fence(text) == "print('hi')\n"


def test_the_code_inside_the_fence_is_kept_as_it_is():
    """The code inside the fence is not changed."""
    text = "```python\n\n    indented = True\n\n```"

    assert strip_code_fence(text) == "\n    indented = True\n\n"


def test_an_unfenced_text_is_unchanged():
    """Text without a fence is returned as it is."""
    text = "print('hi')\n"

    assert strip_code_fence(text) == text


def test_an_empty_text_is_unchanged():
    """Empty text is returned as it is."""
    assert strip_code_fence("") == ""


def test_a_text_with_only_an_opening_fence_is_unchanged():
    """A fence is removed only when both ends have one."""
    text = "```\nprint('hi')"

    assert strip_code_fence(text) == text


def test_a_text_with_only_a_closing_fence_is_unchanged():
    """A fence is removed only when both ends have one."""
    text = "print('hi')\n```"

    assert strip_code_fence(text) == text


def test_the_prompt_carries_the_conventions():
    """The composed prompt holds the text of the project conventions."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    assert conventions_text().strip() in prompt


def test_the_conventions_come_after_the_pack_prompt():
    """The conventions follow the prompt of the pack."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    assert prompt.index(PACK_PROMPT) < prompt.index(conventions_text().strip())


def test_the_conventions_come_before_the_requirement():
    """The conventions come before the requirement of the task."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    assert prompt.index(conventions_text().strip()) < prompt.index(REQUIREMENT)


def test_the_prompt_names_every_convention():
    """The prompt names the rules C1 to C6."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    for rule in ("C1", "C2", "C3", "C4", "C5", "C6"):
        assert rule in prompt


def test_the_other_sections_keep_their_order():
    """The sections around the conventions keep their order."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    positions = [
        prompt.index(section)
        for section in (
            CORE_INSTRUCTION.strip(),
            PACK_PROMPT,
            REQUIREMENT,
            OUTPUT_CONTRACT.strip(),
        )
    ]

    assert positions == sorted(positions)


def test_every_section_appears_once():
    """No section of the prompt is removed or duplicated."""
    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT)

    sections = (
        CORE_INSTRUCTION.strip(),
        PACK_PROMPT,
        conventions_text().strip(),
        REQUIREMENT,
        OUTPUT_CONTRACT.strip(),
    )

    for section in sections:
        assert prompt.count(section) == 1


def test_the_same_inputs_give_the_same_prompt():
    """The composition is deterministic."""
    first = compose_prompt(PACK_PROMPT, REQUIREMENT)
    second = compose_prompt(PACK_PROMPT, REQUIREMENT)

    assert first == second


def test_the_same_inputs_give_the_same_version():
    """The same prompt always gives the same version."""
    first = compose_prompt(PACK_PROMPT, REQUIREMENT)
    second = compose_prompt(PACK_PROMPT, REQUIREMENT)

    assert prompt_version(first) == prompt_version(second)


def test_the_version_changes_when_the_conventions_change(monkeypatch):
    """A different convention text gives a different prompt and version."""
    first = compose_prompt(PACK_PROMPT, REQUIREMENT)

    monkeypatch.setattr(prompt_module, "conventions_text",
                        lambda: "C1 changed")

    second = compose_prompt(PACK_PROMPT, REQUIREMENT)

    assert first != second
    assert prompt_version(first) != prompt_version(second)


def test_the_prompt_without_feedback_is_the_phase_six_prompt():
    """The prompt without feedback is the five-section prompt of Phase 6."""
    expected = "\n\n".join([
        CORE_INSTRUCTION.strip(), PACK_PROMPT, conventions_text().strip(),
        REQUIREMENT, OUTPUT_CONTRACT.strip(),
    ])

    assert compose_prompt(PACK_PROMPT, REQUIREMENT) == expected
    assert compose_prompt(PACK_PROMPT, REQUIREMENT, "") == expected
    assert compose_prompt(PACK_PROMPT, REQUIREMENT, "   \n ") == expected


@pytest.mark.parametrize("task, part, version", [
    ("plate_2holes", "plt0001", "9e23f5e3af8db9d8"),
    ("plate_fillet", "plt0002", "b10c463b8cc296fc"),
])
def test_the_committed_prompt_versions_are_unchanged(task, part, version):
    """The prompt of every committed task keeps its current deterministic version."""
    pack_prompt = (REPO_ROOT / "packs" / "freecad" / "prompt"
                   / "agent.md").read_text(encoding="utf-8")
    requirement = (REPO_ROOT / "evals" / "tasks" / task / "project"
                   / "requirements" / f"{part}.md").read_text(encoding="utf-8")

    assert prompt_version(compose_prompt(pack_prompt, requirement)) == version


def test_the_feedback_comes_between_the_requirement_and_the_contract():
    """A prompt with feedback has six sections and the feedback is in the middle."""
    feedback = "## Repair"

    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT, feedback)

    sections = prompt.split("\n\n")
    assert len(sections) == 6
    assert sections[3] == REQUIREMENT
    assert sections[4] == feedback
    assert sections[5] == OUTPUT_CONTRACT.strip()
    assert prompt_version(prompt) != prompt_version(
        compose_prompt(PACK_PROMPT, REQUIREMENT))


def test_a_long_feedback_is_kept_whole_and_in_the_middle():
    """A feedback block with lines of its own is kept whole, in the middle."""
    feedback = "## Repair\n\nThe previous file is replaced by the file you write now."

    prompt = compose_prompt(PACK_PROMPT, REQUIREMENT, feedback)

    assert feedback in prompt
    assert prompt.index(REQUIREMENT) < prompt.index(feedback)
    assert prompt.index(feedback) < prompt.index(OUTPUT_CONTRACT.strip())
