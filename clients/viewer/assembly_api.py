"""Read an assembly workspace and serialize its portable payload.

An assembly workspace is the output folder of one assembly: it holds the
compound STEP file and an `assembly_result.toml` that describes the verdict of
the assembly. The payload holds no host path, so it can be sent to the browser
as it is.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

ASSEMBLY_MANIFEST_NAME = "assembly_result.toml"


class AssemblyWorkspaceError(ValueError):
    """Raised when an assembly workspace cannot be read."""


def is_assembly_workspace(directory: Path) -> bool:
    """True when the folder holds the result file of an assembly."""
    return (Path(directory) / ASSEMBLY_MANIFEST_NAME).is_file()


def read_assembly_manifest(directory: Path) -> dict[str, Any]:
    """Read the result file of an assembly and return the table it holds."""
    path = Path(directory) / ASSEMBLY_MANIFEST_NAME
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AssemblyWorkspaceError(
            f"the assembly result file {path.name} is unreadable: {exc}") from exc


def assembly_payload(directory: Path) -> dict[str, Any] | None:
    """Return the portable payload of an assembly workspace, or None.

    A folder that holds no assembly result file is not an assembly workspace,
    so the payload is None and the caller keeps its own behaviour.
    """
    if not is_assembly_workspace(directory):
        return None
    manifest = read_assembly_manifest(directory)
    return {
        "assembly_id": _text(manifest.get("assembly_id")),
        "assembly_name": _text(manifest.get("assembly_name")),
        "status": _text(manifest.get("status")),
        "component_count": _count(manifest.get("component_count")),
        "all_valid": manifest.get("all_valid") is True,
        "has_interference": manifest.get("has_interference") is True,
        "all_mates_ok": manifest.get("all_mates_ok") is True,
        "total_volume": _number(manifest.get("total_volume")),
        "bbox_size": _floats(manifest.get("bbox_size")),
        "pairs": _pairs(manifest.get("pairs")),
    }


def _pairs(raw: Any) -> list[dict[str, Any]]:
    """Return the pairwise verdicts of an assembly."""
    if not isinstance(raw, list):
        return []
    return [_pair(entry) for entry in raw]


def _pair(raw: Any) -> dict[str, Any]:
    """Return one pairwise verdict of an assembly."""
    if not isinstance(raw, dict):
        return {}
    return {
        "part_a": _text(raw.get("part_a")),
        "part_b": _text(raw.get("part_b")),
        "intersects": raw.get("intersects") is True,
        "overlap_volume_mm3": _number(raw.get("overlap_volume_mm3")),
        "min_clearance_mm": _number(raw.get("min_clearance_mm")),
        "mate_ok": raw.get("mate_ok") is True,
        "note": _text(raw.get("note")),
    }


def _text(raw: Any) -> str:
    """Return a text, or an empty text when the value is not one."""
    return raw if isinstance(raw, str) else ""


def _count(raw: Any) -> int:
    """Return a count, or zero when the value is not one."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        return 0
    return raw


def _number(raw: Any) -> float:
    """Return a number, or zero when the value is not one."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    return float(raw)


def _floats(raw: Any) -> list[float]:
    """Return three numbers, or an empty list when the value is not one."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        return []
    return [_number(value) for value in raw]
