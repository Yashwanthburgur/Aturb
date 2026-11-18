"""Static safety check for part files, run before the CAD is ever launched."""

from __future__ import annotations

import ast

ALLOWED_IMPORTS = {"FreeCAD", "Part", "PartDesign", "Sketcher", "math"}
BANNED_CALLS = {
    "open", "exec", "eval", "compile", "__import__", "input", "globals",
    "locals", "vars", "getattr", "setattr", "delattr", "breakpoint",
}


def precheck(source: str) -> tuple[str, list[str]]:
    """Return ("ok", []) or ("syntax_error", [msg]) or ("rejected_unsafe", [reasons])."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ("syntax_error", [str(exc)])

    reasons: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    reasons.append(
                        f"line {node.lineno}: import of {alias.name!r} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in ALLOWED_IMPORTS:
                reasons.append(
                    f"line {node.lineno}: import from {node.module!r} is not allowed")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                reasons.append(
                    f"line {node.lineno}: call to {func.id}() is banned")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                reasons.append(
                    f"line {node.lineno}: dunder attribute {node.attr!r} is banned")

    if reasons:
        return ("rejected_unsafe", reasons)
    return ("ok", [])
