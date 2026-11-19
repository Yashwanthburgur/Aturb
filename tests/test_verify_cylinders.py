"""Tests for the cylindrical face classification.

The committed fixture is a 120 x 60 x 5 plate with two 10 mm through-holes at
X = -40 and X = +40, so both hole walls are full cylindrical bands of radius 5
and height 5.

The other two models are written on the fly with build123d calls that are
recorded in docs/api_notes/build123d.md.
"""

from __future__ import annotations

from pathlib import Path

from build123d import Box, GeomType, Location, export_step
from build123d import Cylinder as B3dCylinder

from aturb.verify.cylinders import Cylinder, cylindrical_faces
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

TOL = 0.01  # starting default


def _at(found: list[Cylinder], x: float) -> Cylinder:
    """Return the one cylinder whose axis sits at the given X."""
    matches = [c for c in found if abs(c.axis_x - x) <= TOL]
    assert len(
        matches) == 1, f"expected one cylinder at X={x}, got {len(matches)}"
    return matches[0]


def test_fixture_has_two_cylindrical_faces():
    """The plate fixture holds two cylindrical faces."""
    found = cylindrical_faces(load_step(FIXTURE_PATH))

    assert len(found) == 2


def test_planar_faces_are_excluded():
    """The six planar faces of the plate are not classified."""
    model = load_step(FIXTURE_PATH)
    planar = [face for face in model.faces if face.geom_type == GeomType.PLANE]

    assert len(planar) == 6
    assert len(cylindrical_faces(model)) == 2


def test_cylinder_radius():
    """Both hole walls have radius 5.0."""
    found = cylindrical_faces(load_step(FIXTURE_PATH))

    assert all(abs(c.radius - 5.0) <= TOL for c in found)


def test_cylinder_axis_position():
    """The hole axes sit at X = -40 and X = +40, on Y = 0 and Z = 0."""
    found = cylindrical_faces(load_step(FIXTURE_PATH))

    for x in (-40.0, 40.0):
        cylinder = _at(found, x)
        assert abs(cylinder.axis_y) <= TOL
        assert abs(cylinder.axis_z) <= TOL


def test_cylinder_axis_direction():
    """Both hole axes point along Z."""
    found = cylindrical_faces(load_step(FIXTURE_PATH))

    for cylinder in found:
        assert abs(cylinder.direction_x) <= TOL
        assert abs(cylinder.direction_y) <= TOL
        assert abs(cylinder.direction_z - 1.0) <= TOL


def test_cylinder_height():
    """Both hole walls are 5.0 tall."""
    found = cylindrical_faces(load_step(FIXTURE_PATH))

    assert all(abs(c.height - 5.0) <= TOL for c in found)


def test_cylinders_are_through():
    """A hole wall bounded by two circles is a through candidate."""
    found = cylindrical_faces(load_step(FIXTURE_PATH))

    assert all(c.through for c in found)


def test_model_without_cylindrical_faces(tmp_path):
    """A plain box has no cylindrical face at all."""
    path = tmp_path / "box.step"
    export_step(Box(20, 20, 10), str(path))

    assert cylindrical_faces(load_step(path)) == []


def test_cylinder_without_two_circular_edges_is_not_through(tmp_path):
    """A cylindrical face with no circular edge is not a through candidate.

    Two crossed cylinders meet along curves that are not circles, so none of
    their four cylindrical faces is bounded by two circles.
    """
    vertical = B3dCylinder(3, 6)
    horizontal = B3dCylinder(3, 6).moved(Location((0, 0, 0), (90, 0, 0)))
    path = tmp_path / "crossed.step"
    export_step(vertical & horizontal, str(path))

    found = cylindrical_faces(load_step(path))

    assert len(found) == 4
    assert not any(c.through for c in found)
