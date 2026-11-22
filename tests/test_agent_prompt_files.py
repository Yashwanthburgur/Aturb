"""Tests for the prompt files of the packs.

Every pack that declares a prompt folder holds an agent prompt, every task ID
that a prompt cites exists in the API note of that pack, and the FreeCAD prompt
states the file contract and the output contract. The core holds no prompt:
the packs own them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from aturb.packs import discover
from packs.freecad import helper as freecad_helper

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKS_ROOT = REPO_ROOT / "packs"
API_NOTES_DIR = REPO_ROOT / "docs" / "api_notes"
PROMPT_FILE_NAME = "agent.md"

TASK_ID = re.compile(r"T\d+\.\d+")
HELPER_CALL = re.compile(r"helper\.(\w+)\(")

# The public calls of the selection helper of the FreeCAD pack.
HELPER_CALLS = sorted(freecad_helper.__all__)

MANIFESTS = discover(PACKS_ROOT)
PACK_NAMES = sorted(MANIFESTS)


def _prompt_path(pack_name: str) -> Path:
    """Return the agent prompt of one pack."""
    manifest = MANIFESTS[pack_name]
    return manifest.pack_dir / manifest.prompt_dir / PROMPT_FILE_NAME


def _prompt_text(pack_name: str) -> str:
    """Return the text of the agent prompt of one pack."""
    return _prompt_path(pack_name).read_text(encoding="utf-8")


def _note_path(pack_name: str) -> Path:
    """Return the API note of one pack."""
    return API_NOTES_DIR / f"{pack_name}.md"


def _flat(text: str) -> str:
    """Return the text with its line breaks turned into single spaces.

    A prompt is wrapped for reading, so a phrase may cross a line break. The
    tests look for phrases, not for the place where the author wrapped them.
    """
    return " ".join(text.split())


@pytest.mark.parametrize("pack_name", PACK_NAMES)
def test_every_pack_with_a_prompt_dir_has_an_agent_prompt(pack_name):
    """Every pack that declares a prompt folder holds an agent prompt."""
    assert _prompt_path(pack_name).is_file()


@pytest.mark.parametrize("pack_name", PACK_NAMES)
def test_every_cited_task_id_exists_in_the_api_note(pack_name):
    """Every task ID a pack prompt cites exists in the API note of that pack."""
    cited = set(TASK_ID.findall(_prompt_text(pack_name)))
    note = _note_path(pack_name)
    if not note.is_file():
        assert cited == set()
        return
    known = set(TASK_ID.findall(note.read_text(encoding="utf-8")))
    assert cited <= known


def test_the_freecad_prompt_names_the_file_contract():
    """The FreeCAD prompt states the file contract of the pack."""
    text = _prompt_text("freecad")

    assert "## File contract" in text
    assert "build(doc)" in text


def test_the_freecad_prompt_names_the_output_contract():
    """The FreeCAD prompt states the output contract."""
    text = _prompt_text("freecad")

    assert "## Output contract" in text
    assert "nothing else" in text


def test_the_freecad_prompt_names_the_helper():
    """The FreeCAD prompt names the helper and the global it arrives under."""
    text = _flat(_prompt_text("freecad"))

    assert "## The selection helper" in text
    assert "`helper`" in text
    assert "do not import it" in text


def test_the_freecad_prompt_states_the_boundary_of_the_helper():
    """The prompt states what the helper does and what it never does."""
    text = _flat(_prompt_text("freecad"))

    assert "selects, measures and asserts" in text
    assert "never creates a feature" in text
    assert "You still create the feature and set its parameters" in text


def test_the_freecad_prompt_states_the_selection_rule():
    """The prompt states that selection is by property and never by index."""
    text = _flat(_prompt_text("freecad"))

    assert "by geometric property" in text
    assert "never by an assumed positional index" in text


def test_the_freecad_prompt_names_every_call_of_the_helper():
    """Every public call of the helper is named in the pack prompt."""
    text = _flat(_prompt_text("freecad"))

    for name in HELPER_CALLS:
        assert f"helper.{name}(" in text


def test_the_freecad_prompt_names_no_call_the_helper_does_not_have():
    """Every helper call the prompt names exists in the helper module."""
    text = _flat(_prompt_text("freecad"))

    named = set(HELPER_CALL.findall(text))

    assert named <= set(HELPER_CALLS)


def test_the_freecad_prompt_names_no_task_and_no_expected_value():
    """The pack prompt leaks no task of the set and no expected value."""
    text = _flat(_prompt_text("freecad"))

    assert "plate_2holes" not in text
    assert "plt0001" not in text
    assert "35214" not in text
    assert "35175" not in text


def test_the_stub_prompt_names_the_file_contract():
    """The stub prompt states the file contract of the pack."""
    text = _prompt_text("stub")

    assert "## File contract" in text
    assert ".stub" in text


def test_no_prompt_file_lives_in_the_core():
    """The core holds no prompt; the packs own them."""
    assert list((REPO_ROOT / "aturb").rglob(PROMPT_FILE_NAME)) == []
