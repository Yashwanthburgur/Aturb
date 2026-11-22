"""The FreeCAD helper: it selects, measures and asserts, and creates nothing.

The API lives in the sibling module `select.py`, which imports nothing from
this package, so the CAD can load that module by path. This facade is for the
repository-side import `from packs.freecad.helper import select`.
"""

from .select import (
    assert_count,
    assert_radius,
    bottom_faces,
    circular_edges,
    corner_edges,
    cylindrical_faces,
    edge_length,
    edge_points,
    edge_type,
    face_area,
    face_center,
    face_normal,
    faces_by_normal,
    top_faces,
    vertical_edges,
)

__all__ = [
    "assert_count", "assert_radius", "bottom_faces", "circular_edges",
    "corner_edges", "cylindrical_faces", "edge_length", "edge_points",
    "edge_type", "face_area", "face_center", "face_normal",
    "faces_by_normal", "top_faces", "vertical_edges",
]
