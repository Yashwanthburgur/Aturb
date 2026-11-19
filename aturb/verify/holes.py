"""Find the holes of a part from its exported STEP.

A hole is a cylindrical face whose material lies outside the cylinder, so the
face bounds a void. The evidence is the face normal: the normal of a solid
points away from the material, so it points towards the cylinder axis when the
cylinder is a void and away from the axis when the cylinder is solid material
such as a boss.

A hole is through when its axis meets no material anywhere in the part. The
evidence is the intersection of the axis line with the model: an empty result
means the axis runs through open space from end to end. The test is
conservative, so a hole whose axis crosses other material is not called
through.

The build123d calls used here were verified in-session against build123d
0.13.0. The ones already in docs/api_notes/build123d.md are marked there; the
new ones are Edge.make_line, Face.normal_at, Edge.start_point and the vector
helpers Vector.dot and Vector.length.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import Edge, Face, Vector

from aturb.verify.cylinders import cylinder_faces
from aturb.verify.step import StepModel

OFF_AXIS_FRACTION = 0.5  # starting default


@dataclass(frozen=True)
class Hole:
    """One hole of a part, described in neutral terms.

    The position is the point on the hole axis at the middle of the hole along
    that axis.
    """

    diameter: float
    x: float
    y: float
    z: float
    through: bool


def find_holes(model: StepModel) -> list[Hole]:
    """Report the holes of the model, sorted by x, then y, then z."""
    holes: list[Hole] = []
    for face in cylinder_faces(model):
        hole = _describe(face, model)
        if hole is not None:
            holes.append(hole)
    holes.sort(key=lambda hole: (hole.x, hole.y, hole.z))
    return holes


def _describe(face: Face, model: StepModel) -> Hole | None:
    """Read one cylindrical face as a hole, or None when it is not one."""
    axis = face.axis_of_rotation
    radius = face.radius
    if axis is None or radius is None:
        return None
    point = _off_axis_point(face, axis.position, axis.direction, radius)
    if point is None:
        return None
    # The normal of a face points away from the material of the solid, so it
    # points towards the axis when the cylinder is a void.
    normal = face.normal_at(point)
    if normal.dot(axis.position - point) <= 0:
        return None
    middle = _axis_middle(face, axis.position, axis.direction)
    return Hole(
        diameter=2 * radius,
        x=middle.X,
        y=middle.Y,
        z=middle.Z,
        through=_axis_is_clear(model, axis.position, axis.direction),
    )


def _off_axis_point(
    face: Face,
    axis_point: Vector,
    axis_direction: Vector,
    radius: float,
) -> Vector | None:
    """A point on the face that is clearly away from the cylinder axis.

    The seam line of a cylinder starts on the axis, so every edge is tried and
    the first point that is clearly off the axis is used.
    """
    for edge in face.edges():
        point = edge.start_point()
        distance = _radial_distance(point, axis_point, axis_direction)
        if distance > radius * OFF_AXIS_FRACTION:
            return point
    return None


def _radial_distance(
    point: Vector,
    axis_point: Vector,
    axis_direction: Vector,
) -> float:
    """Distance from a point to the cylinder axis line."""
    offset = point - axis_point
    radial = offset - axis_direction * offset.dot(axis_direction)
    return radial.length


def _axis_middle(
    face: Face,
    axis_point: Vector,
    axis_direction: Vector,
) -> Vector:
    """The point on the axis at the middle of the face extent along the axis.

    The extent comes from the bounding box of the face, so it is exact for a
    full cylindrical band and an over-estimate for a partial one.
    """
    box = face.bounding_box()
    corners = [
        Vector(x, y, z)
        for x in (box.min.X, box.max.X)
        for y in (box.min.Y, box.max.Y)
        for z in (box.min.Z, box.max.Z)
    ]
    steps = [(corner - axis_point).dot(axis_direction) for corner in corners]
    middle = (min(steps) + max(steps)) / 2
    return axis_point + axis_direction * middle


def _axis_is_clear(
    model: StepModel,
    axis_point: Vector,
    axis_direction: Vector,
) -> bool:
    """True when the axis line meets no material in the model."""
    size = model.bbox_size
    span = (size.X ** 2 + size.Y ** 2 + size.Z ** 2) ** 0.5
    line = Edge.make_line(
        axis_point - axis_direction * span,
        axis_point + axis_direction * span,
    )
    common = model.shape & line
    if common is None:
        return True
    return not any(edge.length > 0 for edge in common.edges())
