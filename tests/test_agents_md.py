"""Guards for the AGENTS.md contract that every agent in this repo must follow."""

from pathlib import Path

AGENTS_MD = Path(__file__).resolve().parent.parent / "AGENTS.md"


def test_agents_md_exists():
    assert AGENTS_MD.is_file()


def test_agents_md_short():
    lines = AGENTS_MD.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 60


def test_agents_md_key_rules():
    text = AGENTS_MD.read_text(encoding="utf-8")
    assert "uv run pytest" in text
    assert "operations layer" in text
