"""Measure the gap between two parts from their exported STEP.

The distance is the smallest distance between any solid of one model and any
solid of the other, so a model that holds several solids is measured against
its closest solid. The value is in the length unit of the STEP file; the
ATURB fixtures declare millimetres.

``distance_to`` returns 0.0 when two solids overlap, and it returns 0.0 when
they touch as well, so a zero distance means "no gap" and never says which of
the two it is. Telling an overlap from a touch is the job of the interference
check, not of this module.
"""

from __future__ import annotations

from aturb.verify.step import StepModel


def min_distance(a: StepModel, b: StepModel) -> float:
    """The smallest distance between any solid of a and any solid of b.

    The value is in the length unit of the STEP files. It is 0.0 when the two
    models touch or overlap. A model without a solid has no distance, so a
    ``ValueError`` is raised for one.
    """
    if not a.solids or not b.solids:
        raise ValueError("both models must hold at least one solid")
    return min(
        first.distance_to(second)
        for first in a.solids
        for second in b.solids
    )


def clearance_ok(a: StepModel, b: StepModel, min_gap: float) -> bool:
    """True when the gap between the two models is at least min_gap.

    A gap of exactly min_gap passes. The gap and the minimum are in the length
    unit of the STEP files.
    """
    return min_distance(a, b) >= min_gap
