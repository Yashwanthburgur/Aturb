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

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKS_ROOT = REPO_ROOT / "packs"
API_NOTES_DIR = REPO_ROOT / "docs" / "api_notes"
PROMPT_FILE_NAME = "agent.md"

TASK_ID = re.compile(r"T\d+\.\d+")

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


def test_the_stub_prompt_names_the_file_contract():
    """The stub prompt states the file contract of the pack."""
    text = _prompt_text("stub")

    assert "## File contract" in text
    assert ".stub" in text


def test_no_prompt_file_lives_in_the_core():
    """The core holds no prompt; the packs own them."""
    assert list((REPO_ROOT / "aturb").rglob(PROMPT_FILE_NAME)) == []
