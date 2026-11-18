"""Guard: the core never statically imports a pack."""

from __future__ import annotations

import ast
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1] / "aturb"


def _is_pack_import(module: str) -> bool:
    """Return True if a module name refers to the packs package."""
    return module == "packs" or module.startswith("packs.")


def test_core_has_no_pack_imports():
    """Fail if any module under aturb/ imports packs or packs.something."""
    offenders: list[str] = []
    for py_file in sorted(CORE_DIR.rglob("*.py")):
        tree = ast.parse(
            py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_pack_import(alias.name):
                        offenders.append(
                            f"{py_file}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if _is_pack_import(module):
                    offenders.append(
                        f"{py_file}:{node.lineno}: from {module} import ...")
    assert not offenders, (
        "the core must not import packs:\n" + "\n".join(offenders))
