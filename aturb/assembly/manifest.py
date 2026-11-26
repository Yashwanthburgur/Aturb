"""The portable manifest of an assembly.

An assembly is declared in a TOML file that names its components and the
clearance windows between them. The manifest holds no host path: every part is
named by its part id, and the core resolves that id inside the project.

The manifest is a declaration, not a geometry language. It places parts and it
states clearances; it never describes a feature and it never carries a shape.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

TOP_LEVEL_KEYS = ("assembly_id", "name", "components", "mates")
REQUIRED_TOP_LEVEL_KEYS = ("assembly_id", "name", "components")
COMPONENT_KEYS = ("name", "part_id", "position", "rotation_deg")
REQUIRED_COMPONENT_KEYS = ("name", "part_id")
MATE_KEYS = ("part_a", "part_b", "min_clearance_mm", "max_clearance_mm")
REQUIRED_MATE_KEYS = ("part_a", "part_b")
MIN_COMPONENTS = 2


class AssemblyError(ValueError):
    """Raised when an assembly manifest cannot be read or is not usable."""


@dataclass(frozen=True)
class AssemblyComponent:
    """One placed component of an assembly.

    The position is a translation in millimetres and the rotation is a turn
    about the X, the Y and the Z axis in degrees. Both are applied to the
    exported STEP of the part, never to the source of the part.
    """

    name: str
    part_id: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)  # starting default
    rotation_deg: tuple[float, float, float] = (
        0.0, 0.0, 0.0)  # starting default


@dataclass(frozen=True)
class MateExpectation:
    """The clearance window expected between two components.

    The window is open at the top when no maximum is given. A minimum of zero
    means the two components may touch, but they may never share material.
    """

    part_a: str
    part_b: str
    min_clearance_mm: float = 0.0  # starting default
    max_clearance_mm: float | None = None  # starting default


@dataclass(frozen=True)
class AssemblySpec:
    """One assembly: its components and the mates between them."""

    assembly_id: str
    name: str
    components: tuple[AssemblyComponent, ...]
    mates: tuple[MateExpectation, ...] = ()  # starting default


def load_assembly(path: Path) -> AssemblySpec:
    """Read an assembly manifest and return the assembly it describes.

    Raises ``AssemblyError`` when the file cannot be read, when it is not valid
    TOML, when a key is missing or unknown, or when the assembly it describes
    cannot be built.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise AssemblyError(
            f"cannot read the assembly manifest {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise AssemblyError(
            f"invalid TOML in the assembly manifest {path}: {exc}") from exc
    _check_keys(data, TOP_LEVEL_KEYS, REQUIRED_TOP_LEVEL_KEYS,
                "the assembly manifest")
    assembly_id = _text(data["assembly_id"], "the assembly_id of the assembly")
    name = _text(data["name"], "the name of the assembly")
    components = _components(data["components"])
    mates = _mates(data.get("mates", []), components)
    return AssemblySpec(
        assembly_id=assembly_id, name=name, components=components, mates=mates)


def _check_keys(table: dict, allowed: tuple[str, ...],
                required: tuple[str, ...], what: str) -> None:
    """Refuse a table that misses a key or holds a key that is not known."""
    missing = sorted(key for key in required if key not in table)
    if missing:
        raise AssemblyError(f"{what} is missing key(s): {', '.join(missing)}")
    unknown = sorted(key for key in table if key not in allowed)
    if unknown:
        raise AssemblyError(f"{what} has unknown key(s): {', '.join(unknown)}")


def _components(raw: object) -> tuple[AssemblyComponent, ...]:
    """Return the components of an assembly, checked one by one."""
    if not isinstance(raw, list):
        raise AssemblyError("the components of the assembly are not a list")
    if len(raw) < MIN_COMPONENTS:
        raise AssemblyError(
            f"an assembly needs at least {MIN_COMPONENTS} components, "
            f"got {len(raw)}")
    components: list[AssemblyComponent] = []
    names: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise AssemblyError("a component of the assembly is not a table")
        _check_keys(entry, COMPONENT_KEYS,
                    REQUIRED_COMPONENT_KEYS, "a component")
        name = _text(entry["name"], "the name of a component")
        part_id = _text(entry["part_id"], "the part id of a component")
        if name in names:
            raise AssemblyError(
                f"the assembly names the component {name!r} twice")
        names.add(name)
        components.append(AssemblyComponent(
            name=name,
            part_id=part_id,
            position=_vector(entry.get("position", (0.0, 0.0, 0.0)),
                             "position", name),
            rotation_deg=_vector(entry.get("rotation_deg", (0.0, 0.0, 0.0)),
                                 "rotation_deg", name),
        ))
    return tuple(components)


def _mates(raw: object, components: tuple[AssemblyComponent, ...]) -> tuple[MateExpectation, ...]:
    """Return the mates of an assembly, checked against its components."""
    if not isinstance(raw, list):
        raise AssemblyError("the mates of the assembly are not a list")
    known = {component.name for component in components}
    mates: list[MateExpectation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise AssemblyError("a mate of the assembly is not a table")
        _check_keys(entry, MATE_KEYS, REQUIRED_MATE_KEYS, "a mate")
        part_a = _text(entry["part_a"], "the first part of a mate")
        part_b = _text(entry["part_b"], "the second part of a mate")
        if part_a == part_b:
            raise AssemblyError(
                f"the mate names the component {part_a!r} twice")
        for known_name in (part_a, part_b):
            if known_name not in known:
                raise AssemblyError(
                    f"the mate names the unknown component {known_name!r}")
        minimum = _number(entry.get("min_clearance_mm", 0.0),
                          "min_clearance_mm")
        if minimum < 0.0:
            raise AssemblyError("the min_clearance_mm of a mate is negative")
        raw_maximum = entry.get("max_clearance_mm")
        maximum = (None if raw_maximum is None
                   else _number(raw_maximum, "max_clearance_mm"))
        if maximum is not None and maximum < minimum:
            raise AssemblyError(
                "the max_clearance_mm of a mate is below its min_clearance_mm")
        mates.append(MateExpectation(
            part_a=part_a, part_b=part_b, min_clearance_mm=minimum,
            max_clearance_mm=maximum))
    return tuple(mates)


def _vector(raw: object, what: str, name: str) -> tuple[float, float, float]:
    """Return three finite numbers, or refuse the value."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise AssemblyError(
            f"the {what} of the component {name!r} is not three numbers")
    values: list[float] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AssemblyError(
                f"the {what} of the component {name!r} is not a number")
        number = float(value)
        if not math.isfinite(number):
            raise AssemblyError(
                f"the {what} of the component {name!r} is not finite")
        values.append(number)
    return (values[0], values[1], values[2])


def _number(raw: object, what: str) -> float:
    """Return one finite number, or refuse the value."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise AssemblyError(f"the {what} of a mate is not a number")
    number = float(raw)
    if not math.isfinite(number):
        raise AssemblyError(f"the {what} of a mate is not finite")
    return number


def _text(raw: object, what: str) -> str:
    """Return a non-empty text, or refuse the value."""
    if not isinstance(raw, str) or not raw.strip():
        raise AssemblyError(f"{what} is not a non-empty text")
    return raw.strip()
