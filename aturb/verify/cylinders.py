"""Classify the cylindrical faces of a neutral STEP model.

Every call used here is recorded in docs/api_notes/build123d.md.

Two facts from that register shape this module:

- ``face.center()`` defaults to ``CenterOf.GEOMETRY`` and reports a point that
  is not on the cylinder axis. The axis position is read with
  ``face.center(CenterOf.MASS)`` instead.
- The height of a cylindrical face is derived from its area with
  ``area / (2 * pi * radius)``. That holds for a full cylindrical band only, so
  the height of a partial band is not the height of the underlying cylinder.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import CenterOf, Face, GeomType

from aturb.verify.step import StepModel


@dataclass(frozen=True)
class Cylinder:
    """One cylindrical face of a model, described in neutral terms.

    The axis point is the mass centre of the face, which lies on the axis of a
    full cylindrical band. The direction is the axis direction. ``through`` is
    the two-circular-edge test: it marks a face that is bounded by two circles,
    which is a through-cylinder candidate and not a proof that the hole leaves
    the part.
    """

    radius: float
    axis_x: float
    axis_y: float
    axis_z: float
    direction_x: float
    direction_y: float
    direction_z: float
    height: float
    through: bool


def cylinder_faces(model: StepModel) -> list[Face]:
    """The cylindrical faces of the model, in the order the model holds them."""
    return [face for face in model.faces if face.geom_type == GeomType.CYLINDER]


def cylindrical_faces(model: StepModel) -> list[Cylinder]:
    """Describe every cylindrical face of the model.

    The faces are returned in the order the model holds them.
    """
    return [_describe(face) for face in cylinder_faces(model)]


def _describe(face: Face) -> Cylinder:
    """Read one cylindrical face into a neutral description."""
    radius = face.radius
    axis = face.center(CenterOf.MASS)
    direction = face.axis_of_rotation.direction
    height = face.area / (2 * math.pi * radius)
    return Cylinder(
        radius=radius,
        axis_x=axis.X,
        axis_y=axis.Y,
        axis_z=axis.Z,
        direction_x=direction.X,
        direction_y=direction.Y,
        direction_z=direction.Z,
        height=height,
        through=_circular_edge_count(face) == 2,
    )


def _circular_edge_count(face: Face) -> int:
    """Count the circular edges that bound one face."""
    return sum(1 for edge in face.edges() if edge.geom_type == GeomType.CIRCLE)
