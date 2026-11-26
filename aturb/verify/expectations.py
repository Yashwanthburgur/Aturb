"""Read the expected values of a part and turn them into check results.

An expectation file holds numbers only: the measurements a part must meet. It
holds no geometry, no feature tree and no CAD operation, so the same file
judges a part whatever built it.

The file is authoritative input. It is written by hand from the parameters of
the part, never from a measured file, and the agent may not change it without
a declared reason.

The schema is:

- ``volume``: the expected volume of the part.
- ``bbox``: the expected size of the bounding box, as x, y and z.
- ``hole_count``: the expected number of holes.
- ``hole_diameter``: the expected diameter of every hole.
- ``hole_positions``: the expected position of every hole, as x and y.

One optional value may be added:

- ``hole_diameters``: the expected diameter of every hole, one per hole, in
  the order of ``hole_positions``. It names the holes that do not share one
  diameter, such as a stepped bore and its counterbore. When it is absent the
  scalar ``hole_diameter`` names the diameter of every hole, as before.

A hole position is where the hole sits in the plane of the part. The height
of a through-hole is the middle of the plate, which says how the part is
placed rather than where the hole is, so it is not expected here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from aturb.verify.holes import Hole, find_holes
from aturb.verify.result import CheckResult
from aturb.verify.step import StepModel

TOLERANCE = 0.01  # starting default

REQUIRED_KEYS = ("volume", "bbox", "hole_count",
                 "hole_diameter", "hole_positions")
OPTIONAL_KEYS = ("hole_diameters",)


def load_expectations(path: Path) -> dict:
    """Load the expected values of a part from a TOML file.

    The values are returned as the file holds them; the loader checks them
    but never changes them. A missing file raises ``FileNotFoundError``. A
    file that is not valid TOML, or that does not hold the expected values,
    raises ``ValueError``.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    _validate(raw)
    return raw


def checks_from_expectations(model: StepModel, expected: dict) -> list[CheckResult]:
    """Turn every expected value into a result.

    One expected value can give more than one result: the bounding box gives
    one result per axis, and every hole gives its own diameter and position
    results. Without per-hole diameters the holes are compared in the order
    they are reported, which is sorted by x and then y. With them every hole is
    compared with the hole that sits at its own place.
    """
    values = _validate(expected)
    results: list[CheckResult] = []
    results.append(_measurement("volume", values["volume"], model.volume))
    size = model.bbox_size
    for axis, value in zip("xyz", values["bbox"], strict=True):
        results.append(_measurement(
            f"bbox_{axis}", value, getattr(size, axis.upper())))
    holes = find_holes(model)
    results.append(_measurement(
        "hole_count", values["hole_count"], len(holes)))
    results.extend(_diameter_results(values, holes))
    results.extend(_position_results(values, holes))
    return results


def _measurement(name: str, expected: float, actual: float) -> CheckResult:
    """One result from an expected number and a measured number."""
    return CheckResult.from_measurement(name, expected, actual, TOLERANCE)


def _diameter_results(values: dict, holes: list[Hole]) -> list[CheckResult]:
    """One result for the diameter of every hole.

    With per-hole diameters every hole is measured against the diameter that
    belongs to its own place, so a coaxial bore and its counterbore are each
    measured against their own diameter.
    """
    if not holes:
        if values["hole_count"] == 0:
            return []
        return [
            CheckResult.failure(
                "hole_diameter", "the model holds no hole to measure")
        ]
    if "hole_diameters" not in values:
        return [
            _measurement(f"hole_{index}_diameter",
                         values["hole_diameter"], hole.diameter)
            for index, hole in enumerate(holes)
        ]
    results: list[CheckResult] = []
    for index, (expected, found) in enumerate(_pair_holes(values, holes)):
        if found is None:
            results.append(CheckResult.failure(
                f"hole_{index}_diameter",
                "the model holds no hole at the expected place"))
            continue
        results.append(_measurement(f"hole_{index}_diameter",
                                    expected[2], holes[found].diameter))
    return results


def _position_results(values: dict, holes: list[Hole]) -> list[CheckResult]:
    """One result for the x and the y of every expected hole.

    With per-hole diameters every expected hole is compared with the hole that
    was paired with it, so the place and the diameter of one hole always belong
    together.
    """
    results: list[CheckResult] = []
    if "hole_diameters" in values:
        for index, (expected, found) in enumerate(_pair_holes(values, holes)):
            if found is None:
                results.append(CheckResult.failure(
                    f"hole_{index}",
                    "the model holds no hole at the expected place"))
                continue
            hole = holes[found]
            results.append(_measurement(
                f"hole_{index}_x", expected[0], hole.x))
            results.append(_measurement(
                f"hole_{index}_y", expected[1], hole.y))
        return results
    for index, (x, y) in enumerate(sorted(values["hole_positions"])):
        if index >= len(holes):
            results.append(
                CheckResult.failure(
                    f"hole_{index}", "the model holds fewer holes than expected"
                )
            )
            continue
        hole = holes[index]
        results.append(_measurement(f"hole_{index}_x", x, hole.x))
        results.append(_measurement(f"hole_{index}_y", y, hole.y))
    return results


def _pair_holes(
    values: dict,
    holes: list[Hole],
) -> list[tuple[tuple[float, float, float], int | None]]:
    """Pair every expected hole with the detected hole that belongs to it.

    The expected holes are sorted by x, then y, then diameter, so the order is
    the same whatever order the file lists them in. Among the detected holes at
    the same place the one whose diameter is closest to the expected one is
    taken, so two coaxial holes of different diameters are paired one by one.
    """
    expected = sorted(
        (x, y, diameter)
        for (x, y), diameter in zip(values["hole_positions"],
                                    values["hole_diameters"], strict=True))
    taken: set[int] = set()
    pairs: list[tuple[tuple[float, float, float], int | None]] = []
    for hole in expected:
        gaps: list[tuple[float, int]] = []
        for index, candidate in enumerate(holes):
            if index in taken:
                continue
            distance = max(abs(candidate.x - hole[0]),
                           abs(candidate.y - hole[1]))
            if distance <= TOLERANCE:
                gaps.append((abs(candidate.diameter - hole[2]), index))
        best = min(gaps)[1] if gaps else None
        if best is not None:
            taken.add(best)
        pairs.append((hole, best))
    return pairs


def _validate(raw: dict) -> dict:
    """Check the expected values and return them in a usable shape.

    The file must hold every expected value and nothing else, and every value
    must be a number. The optional per-hole diameters are returned only when
    the file names them, so a file without them holds exactly the values it
    held before.
    """
    if not isinstance(raw, dict):
        raise ValueError("the expectation file must hold a table of values")
    unknown = sorted(set(raw) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS))
    if unknown:
        raise ValueError(f"unknown expected values: {', '.join(unknown)}")
    missing = [key for key in REQUIRED_KEYS if key not in raw]
    if missing:
        raise ValueError(f"missing expected values: {', '.join(missing)}")
    volume = _number(raw["volume"], "volume")
    if volume < 0:
        raise ValueError("the expected volume cannot be negative")
    bbox = _numbers(raw["bbox"], "bbox", 3)
    if any(size < 0 for size in bbox):
        raise ValueError("the expected bounding box cannot be negative")
    hole_count = _count(raw["hole_count"], "hole_count")
    hole_diameter = _number(raw["hole_diameter"], "hole_diameter")
    if hole_diameter < 0:
        raise ValueError("the expected hole diameter cannot be negative")
    positions = _positions(raw["hole_positions"], "hole_positions")
    if len(positions) != hole_count:
        raise ValueError(
            "the expected hole count and the expected hole positions disagree"
        )
    values = {
        "volume": volume,
        "bbox": bbox,
        "hole_count": hole_count,
        "hole_diameter": hole_diameter,
        "hole_positions": positions,
    }
    if "hole_diameters" in raw:
        diameters = _diameters(raw["hole_diameters"], "hole_diameters")
        if len(diameters) != len(positions):
            raise ValueError(
                "the expected hole diameters and the expected hole positions "
                "disagree"
            )
        values["hole_diameters"] = diameters
    return values


def _number(value, name: str) -> float:
    """Return a value as a number, or raise when it is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the expected {name} must be a number")
    return float(value)


def _count(value, name: str) -> int:
    """Return a value as a whole number, or raise when it is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"the expected {name} must be a whole number")
    if value < 0:
        raise ValueError(f"the expected {name} cannot be negative")
    return value


def _numbers(value, name: str, length: int) -> list[float]:
    """Return a list of the given length of numbers, or raise."""
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(
            f"the expected {name} must be a list of {length} numbers")
    numbers = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"the expected {name} must hold numbers only")
        numbers.append(float(item))
    return numbers


def _positions(value, name: str) -> list[tuple[float, float]]:
    """Return a list of x and y pairs, or raise."""
    if not isinstance(value, list):
        raise ValueError(f"the expected {name} must be a list of positions")
    positions = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError(
                f"the expected {name} must hold x and y for every hole")
        positions.append((_number(item[0], name), _number(item[1], name)))
    return positions


def _diameters(value, name: str) -> list[float]:
    """Return a list of diameters, or raise."""
    if not isinstance(value, list):
        raise ValueError(f"the expected {name} must be a list of diameters")
    diameters = []
    for item in value:
        diameter = _number(item, name)
        if diameter <= 0:
            raise ValueError(
                f"the expected {name} must hold positive diameters")
        diameters.append(diameter)
    return diameters
