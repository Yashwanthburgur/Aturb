"""Pure helpers for reading FreeCAD feature states.

Kept in its own module so the rule can be unit tested without FreeCAD.
The rule is the one recorded in docs/api_notes/freecad.md (T1.23): a failed
feature shows the "Invalid" flag, a working feature shows "Up-to-date", and a
container that merely holds a failed feature shows "Touched" only.
"""

from __future__ import annotations

INVALID_FLAG = "Invalid"


def failed_feature_names(objects) -> list[str]:
    """Return the names of the objects whose State carries the Invalid flag."""
    return [
        obj.Name for obj in objects
        if INVALID_FLAG in getattr(obj, "State", [])
    ]
