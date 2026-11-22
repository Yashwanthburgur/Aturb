"""Select geometry by its geometric properties.

The helper only selects, measures and asserts: it never creates a feature,
never changes the feature tree and never modifies a shape. Every FreeCAD call
it uses is recorded in docs/api_notes/freecad.md: `shape.Edges`,
`edge.Vertexes`, `vertex.X`, `vertex.Y`, `vertex.Z` and `edge.Length` (T1.25),
and `shape.Faces`, `face.Surface.isPlanar()`, `face.ParameterRange`,
`face.normalAt(u, v)`, `face.Area`, `face.CenterOfMass` and
`face.Surface.Radius` (T6.06a). The radius of a closed circular edge is
derived from its length, because the length of a full circle is its
circumference.
"""

from __future__ import annotations

import math

TOLERANCE_MM = 0.01  # starting default
VERTICAL_TOLERANCE_MM = 1e-6  # starting default
NORMAL_TOLERANCE = 1e-6  # starting default
TWO_PI = 2.0 * math.pi


def _edges(shape):
    """Return every edge of the shape with the name the CAD gives it."""
    return [(f"Edge{index + 1}", edge)
            for index, edge in enumerate(shape.Edges)]


def _edge_by_name(shape, name):
    """Return the edge with the given name."""
    return shape.Edges[int(name.removeprefix("Edge")) - 1]


def _points(edge):
    """Return the coordinates of the vertices of an edge."""
    return [(vertex.X, vertex.Y, vertex.Z) for vertex in edge.Vertexes]


def _is_vertical(edge) -> bool:
    """Tell whether an edge runs along Z."""
    points = _points(edge)
    if len(points) != 2:
        return False
    (x0, y0, z0), (x1, y1, z1) = points
    same_xy = (abs(x0 - x1) <= VERTICAL_TOLERANCE_MM
               and abs(y0 - y1) <= VERTICAL_TOLERANCE_MM)
    return same_xy and abs(z0 - z1) > VERTICAL_TOLERANCE_MM


def _radius_of(edge) -> float:
    """Return the radius of a closed circular edge from its length."""
    return edge.Length / TWO_PI


def vertical_edges(shape) -> list[str]:
    """Return the names of the edges that run along Z."""
    return [name for name, edge in _edges(shape) if _is_vertical(edge)]


def corner_edges(shape, length_mm, width_mm) -> list[str]:
    """Return the names of the vertical edges at the four corners."""
    half_x = length_mm / 2.0
    half_y = width_mm / 2.0
    names = []
    for name, edge in _edges(shape):
        if not _is_vertical(edge):
            continue
        x, y, _ = _points(edge)[0]
        if (abs(abs(x) - half_x) <= TOLERANCE_MM
                and abs(abs(y) - half_y) <= TOLERANCE_MM):
            names.append(name)
    return names


def circular_edges(shape, radius_mm, tolerance_mm=TOLERANCE_MM) -> list[str]:
    """Return the names of the closed circular edges of the given radius."""
    names = []
    for name, edge in _edges(shape):
        if len(edge.Vertexes) != 1:
            continue
        if abs(_radius_of(edge) - radius_mm) <= tolerance_mm:
            names.append(name)
    return names


def edge_type(shape, name) -> str:
    """Return the type of the named edge: "circle", "line" or "other".

    The type comes from the vertex count (T1.25): one vertex is a closed
    circle, two vertices are a linear edge.
    """
    count = len(_edge_by_name(shape, name).Vertexes)
    if count == 1:
        return "circle"
    if count == 2:
        return "line"
    return "other"


def edge_length(shape, name) -> float:
    """Return the length of the named edge."""
    return _edge_by_name(shape, name).Length


def edge_points(shape, name) -> list[tuple[float, float, float]]:
    """Return the coordinates of the vertices of the named edge."""
    return _points(_edge_by_name(shape, name))


def assert_count(items, expected, label) -> None:
    """Raise when the number of selected items is not the expected one."""
    if len(items) != expected:
        raise AssertionError(
            f"expected {expected} {label}, found {len(items)}")


def assert_radius(shape, names, radius_mm, tolerance_mm=TOLERANCE_MM) -> None:
    """Raise when a selected edge is not a circle of the given radius."""
    for name in names:
        actual = _radius_of(_edge_by_name(shape, name))
        if abs(actual - radius_mm) > tolerance_mm:
            raise AssertionError(
                f"edge {name} has radius {actual:.4f} mm, "
                f"expected {radius_mm} mm")


def _faces(shape):
    """Return every face of the shape with the name the CAD gives it."""
    return [(f"Face{index + 1}", face)
            for index, face in enumerate(shape.Faces)]


def _face_by_name(shape, name):
    """Return the face with the given name."""
    return shape.Faces[int(name.removeprefix("Face")) - 1]


def _normal_of(face) -> tuple[float, float, float]:
    """Return the outward unit normal of a flat face."""
    u_min, u_max, v_min, v_max = face.ParameterRange
    normal = face.normalAt((u_min + u_max) / 2.0, (v_min + v_max) / 2.0)
    return (normal.x, normal.y, normal.z)


def faces_by_normal(shape, nx, ny, nz, tolerance=NORMAL_TOLERANCE) -> list[str]:
    """Return the names of the flat faces whose outward normal matches.

    Only flat faces are considered, so a round face is never picked by the
    normal it happens to have at one point of its surface.
    """
    target = (nx, ny, nz)
    names = []
    for name, face in _faces(shape):
        if not face.Surface.isPlanar():
            continue
        normal = _normal_of(face)
        if all(abs(a - b) <= tolerance for a, b in zip(normal, target, strict=True)):
            names.append(name)
    return names


def top_faces(shape) -> list[str]:
    """Return the names of the flat faces that face up."""
    return faces_by_normal(shape, 0.0, 0.0, 1.0)


def bottom_faces(shape) -> list[str]:
    """Return the names of the flat faces that face down."""
    return faces_by_normal(shape, 0.0, 0.0, -1.0)


def cylindrical_faces(shape, radius_mm, tolerance_mm=TOLERANCE_MM) -> list[str]:
    """Return the names of the round faces of the given radius."""
    names = []
    for name, face in _faces(shape):
        if face.Surface.isPlanar():
            continue
        if abs(face.Surface.Radius - radius_mm) <= tolerance_mm:
            names.append(name)
    return names


def face_normal(shape, name) -> tuple[float, float, float]:
    """Return the outward unit normal of the named face."""
    return _normal_of(_face_by_name(shape, name))


def face_area(shape, name) -> float:
    """Return the area of the named face."""
    return _face_by_name(shape, name).Area


def face_center(shape, name) -> tuple[float, float, float]:
    """Return the centre of mass of the named face."""
    center = _face_by_name(shape, name).CenterOfMass
    return (center.x, center.y, center.z)
