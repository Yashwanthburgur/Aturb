"""The harness that runs inside the CAD must never import the core package."""

from __future__ import annotations

import ast
from pathlib import Path

HARNESS = (
    Path(__file__).resolve().parents[2]
    / "packs" / "freecad" / "harness" / "build_part.py"
)


def test_harness_never_imports_aturb():
    """No import of aturb or any aturb.* module in the harness."""
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("aturb"), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("aturb"), node.module
