"""Tests for the static part-file precheck."""

from __future__ import annotations

from pathlib import Path

import pytest

from packs.freecad.precheck import precheck

REPO_ROOT = Path(__file__).resolve().parents[2]

HELPER_PART_SOURCE = '''"""A part file that uses the injected helper."""


def build(doc):
    """Select the corner edges of the body with the injected helper."""
    edges = helper.corner_edges(doc.Tip.Shape, 120.0, 60.0)
    helper.assert_count(edges, 4, "vertical corner edges")
    return doc.Tip
'''

UNSAFE_SOURCES = [
    "import os",
    "import subprocess",
    "from socket import socket",
    "import urllib.request",
    "open('x.txt', 'w')",
    "eval('1+1')",
    "exec('x=1')",
    "__import__('os')",
    "().__class__.__bases__[0].__subclasses__()",
    "import FreeCAD\ngetattr(FreeCAD, 'ActiveDocument')",
]


@pytest.mark.parametrize("source", UNSAFE_SOURCES)
def test_unsafe_sources_rejected(source):
    """Each planted unsafe pattern is rejected."""
    verdict, reasons = precheck(source)
    assert verdict == "rejected_unsafe"
    assert reasons


def test_demo_part_is_ok():
    """The demo plate passes the precheck."""
    source = (REPO_ROOT / "projects" / "demo" / "parts"
              / "plt0001_base_plate.py").read_text(encoding="utf-8")
    assert precheck(source) == ("ok", [])


def test_syntax_error_detected():
    """A syntactically broken file is reported as syntax_error."""
    verdict, _ = precheck("def build(doc) return 1")
    assert verdict == "syntax_error"


def test_allowed_imports_ok():
    """Allowed imports pass."""
    source = "import math\nimport FreeCAD as App\nfrom Part import LineSegment"
    assert precheck(source) == ("ok", [])


def test_a_part_file_that_uses_the_helper_passes_the_precheck():
    """A part file that only uses the injected helper passes the check."""
    assert precheck(HELPER_PART_SOURCE) == ("ok", [])


def test_a_part_file_that_tries_to_import_the_helper_is_refused():
    """The helper cannot be reached by an import; the check refuses it."""
    source = "import importlib.util\n" + HELPER_PART_SOURCE
    verdict, reasons = precheck(source)
    assert verdict == "rejected_unsafe"
    assert any("importlib.util" in reason for reason in reasons)


def test_a_part_file_that_reaches_for_anything_else_is_refused():
    """A part file that uses the helper and reaches for a file is refused."""
    source = HELPER_PART_SOURCE + "\nopen('helper.py').read()\n"
    verdict, reasons = precheck(source)
    assert verdict == "rejected_unsafe"
    assert any("open()" in reason for reason in reasons)
