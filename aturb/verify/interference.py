"""Detect the material that two solids share, from their exported STEP.

Two solids interfere when they share positive volume. Solids that only touch
share no material: they meet at a face, an edge or a point, so the volume they
share is zero. The distance check in ``aturb/verify/clearance.py`` cannot tell
the two apart, because ``distance_to`` returns 0.0 for a touch and for an
overlap alike.

The intersection is taken with the ``&`` operator, and its result is
normalised here because the operator answers with different shapes depending
on the operands:

- ``Solid & Solid`` returns ``None`` when the solids share no material, and a
  shape when they do.
- ``Compound & Solid`` returns an empty ``Compound`` when they share no
  material.
- ``Shape.intersect()`` returns a ``ShapeList`` for an overlap and ``None``
  otherwise, so it is not used here.

Only the solids inside an intersection count as material. A result that holds
no solid has a volume of zero, whatever shape it is, so a touch is never read
as an interference.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Solid

from aturb.verify.step import StepModel


@dataclass(frozen=True)
class Interference:
    """One pair of solids that share material.

    ``first`` and ``second`` are the positions of the two solids in the model
    they came from, counted from zero. ``volume`` is the material they share,
    in the volume unit of the STEP file.
    """

    first: int
    second: int
    volume: float


def _shared_solids(first: Solid, second: Solid) -> tuple[Solid, ...]:
    """The solids that both shapes hold in common.

    The ``&`` operator answers with ``None`` for two solids that share no
    material, so the result is normalised to a tuple of solids.
    """
    result = first & second
    if result is None:
        return ()
    return tuple(result.solids())


def _shared_volume(first: Solid, second: Solid) -> float:
    """The volume of material two solids share."""
    return sum(solid.volume for solid in _shared_solids(first, second))


def _is_interference(volume: float, tolerance: float) -> bool:
    """True when a shared volume counts as interference.

    The material has to be there: a shared volume of zero is a touch, not an
    interference. The tolerance then says how much material is enough.
    """
    return volume > 0.0 and volume > tolerance


def _require_solids(a: StepModel, b: StepModel) -> None:
    """Raise when either model holds no solid."""
    if not a.solids or not b.solids:
        raise ValueError("both models must hold at least one solid")


def intersection_volume(a: StepModel, b: StepModel) -> float:
    """The volume of material the two models share.

    Every solid of a is measured against every solid of b and the shared
    volumes are added up, so the value is the whole material the two models
    have in common. The value is in the volume unit of the STEP files.
    """
    _require_solids(a, b)
    return sum(
        _shared_volume(first, second)
        for first in a.solids
        for second in b.solids
    )


def interferes(a: StepModel, b: StepModel, tolerance: float = 0.0) -> bool:  # starting default
    """True when the two models share more material than the tolerance.

    The tolerance is a volume, in the volume unit of the STEP files. With the
    default tolerance of 0.0 any shared material counts. Solids that only
    touch do not interfere, because they share no material at all.
    """
    _require_solids(a, b)
    return any(
        _is_interference(_shared_volume(first, second), tolerance)
        for first in a.solids
        for second in b.solids
    )


def find_interferences(
    model: StepModel, tolerance: float = 0.0  # starting default
) -> list[Interference]:
    """Every pair of solids in one model that shares material.

    A model may hold several solids, so every pair of them is checked. The
    pairs come in the order of the solids in the model, and the first solid of
    a pair always comes before the second.
    """
    if not model.solids:
        raise ValueError("the model must hold at least one solid")
    found: list[Interference] = []
    for first_index, first in enumerate(model.solids):
        for second_index in range(first_index + 1, len(model.solids)):
            volume = _shared_volume(first, model.solids[second_index])
            if _is_interference(volume, tolerance):
                found.append(
                    Interference(first=first_index,
                                 second=second_index, volume=volume)
                )
    return found


def find_interferences_between(
    a: StepModel, b: StepModel, tolerance: float = 0.0  # starting default
) -> list[Interference]:
    """Every pair of solids, one from each model, that shares material.

    ``first`` is the position of the solid in a and ``second`` the position of
    the solid in b.
    """
    _require_solids(a, b)
    found: list[Interference] = []
    for first_index, first in enumerate(a.solids):
        for second_index, second in enumerate(b.solids):
            volume = _shared_volume(first, second)
            if _is_interference(volume, tolerance):
                found.append(
                    Interference(first=first_index,
                                 second=second_index, volume=volume)
                )
    return found
