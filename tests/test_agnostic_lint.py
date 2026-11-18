"""Tests for the agnosticism lint."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from agnostic_lint import scan  # noqa: E402


def test_cad_term_is_found(tmp_path):
    """A file that mentions a CAD brand name is reported."""
    target = tmp_path / "core.py"
    target.write_text("import FreeCAD\n", encoding="utf-8")

    findings = scan(tmp_path)

    assert len(findings) == 1
    relative, number, text = findings[0]
    assert relative == "core.py"
    assert number == 1
    assert text == "import FreeCAD"


def test_word_boundary_avoids_false_positive(tmp_path):
    """A word that merely contains a CAD term is not reported."""
    target = tmp_path / "core.py"
    target.write_text("value = 'confusion'\n", encoding="utf-8")

    assert scan(tmp_path) == []


def test_clean_file_has_no_findings(tmp_path):
    """A file with no CAD term produces no findings."""
    target = tmp_path / "core.py"
    target.write_text("x = 1\n", encoding="utf-8")

    assert scan(tmp_path) == []
