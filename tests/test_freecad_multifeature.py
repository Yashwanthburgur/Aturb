"""Multi-feature FreeCAD parts, built in the real CAD and measured neutrally.

Every part is built by the production FreeCADRunner, so the static safety check
runs first, and every number is measured from the exported STEP.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner
from aturb.verify.holes import find_holes
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
VOLUME_TOLERANCE_MM3 = 0.05  # starting default
SIZE_TOLERANCE_MM = 1e-6  # starting default

BOSSED_PLATE = '''"""Bossed plate with a blind pocket and a concentric through-hole.

Units: millimetres. The plate is centred on the origin in X and Y.
"""

PLATE_LENGTH_MM = 100.0
PLATE_WIDTH_MM = 60.0
PLATE_THICKNESS_MM = 8.0
BOSS_DIAMETER_MM = 24.0
BOSS_HEIGHT_MM = 12.0
HOLE_DIAMETER_MM = 10.0
POCKET_LENGTH_MM = 20.0
POCKET_WIDTH_MM = 20.0
POCKET_DEPTH_MM = 4.0
POCKET_CENTRE_X_MM = 32.0


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    def _rect(body, name, length, width, cx=0.0, cy=0.0):
        sk = body.newObject("Sketcher::SketchObject", name)
        x, y = length / 2, width / 2
        pts = [App.Vector(cx - x, cy - y, 0), App.Vector(cx + x, cy - y, 0),
               App.Vector(cx + x, cy + y, 0), App.Vector(cx - x, cy + y, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
        return sk

    body = doc.addObject("PartDesign::Body", "Body")

    plate = body.newObject("PartDesign::Pad", "PlatePad")
    plate.Profile = _rect(body, "PlateSketch", PLATE_LENGTH_MM, PLATE_WIDTH_MM)
    plate.Length = PLATE_THICKNESS_MM
    doc.recompute()

    pocket_sketch = _rect(body, "PocketSketch", POCKET_LENGTH_MM,
                          POCKET_WIDTH_MM, POCKET_CENTRE_X_MM)
    pocket_sketch.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM), App.Rotation())
    pocket = body.newObject("PartDesign::Pocket", "BlindPocket")
    pocket.Profile = pocket_sketch
    pocket.Type = "Length"
    pocket.Length = POCKET_DEPTH_MM
    doc.recompute()

    boss_sketch = body.newObject("Sketcher::SketchObject", "BossSketch")
    boss_sketch.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM), App.Rotation())
    boss_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BOSS_DIAMETER_MM / 2), False)
    boss = body.newObject("PartDesign::Pad", "BossPad")
    boss.Profile = boss_sketch
    boss.Length = BOSS_HEIGHT_MM
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM + BOSS_HEIGHT_MM), App.Rotation())
    hole_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), HOLE_DIAMETER_MM / 2), False)
    hole = body.newObject("PartDesign::Pocket", "ThroughHole")
    hole.Profile = hole_sketch
    hole.Type = "ThroughAll"
    doc.recompute()

    return body
'''

L_BRACKET = '''"""L-bracket with an orthogonal wall, mounting holes and a chamfer.

Units: millimetres. The flange spans X = 0 to FLANGE_LENGTH_MM and the wall
stands on it at X = 0 to WALL_THICKNESS_MM.
"""

FLANGE_LENGTH_MM = 80.0
FLANGE_WIDTH_MM = 50.0
FLANGE_THICKNESS_MM = 8.0
WALL_THICKNESS_MM = 8.0
WALL_HEIGHT_MM = 40.0
HOLE_DIAMETER_MM = 6.0
HOLE_POSITIONS_X_MM = (25.0, 65.0)
CHAMFER_SIZE_MM = 2.0


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    flange_sketch = body.newObject("Sketcher::SketchObject", "FlangeSketch")
    y0 = -FLANGE_WIDTH_MM / 2
    y1 = FLANGE_WIDTH_MM / 2
    pts = [App.Vector(0, y0, 0), App.Vector(FLANGE_LENGTH_MM, y0, 0),
           App.Vector(FLANGE_LENGTH_MM, y1, 0), App.Vector(0, y1, 0)]
    for i in range(4):
        flange_sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
    flange = body.newObject("PartDesign::Pad", "FlangePad")
    flange.Profile = flange_sketch
    flange.Length = FLANGE_THICKNESS_MM
    doc.recompute()

    wall_sketch = body.newObject("Sketcher::SketchObject", "WallSketch")
    wall_sketch.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    z0 = FLANGE_THICKNESS_MM
    z1 = FLANGE_THICKNESS_MM + WALL_HEIGHT_MM
    wpts = [App.Vector(0, z0, 0), App.Vector(WALL_THICKNESS_MM, z0, 0),
            App.Vector(WALL_THICKNESS_MM, z1, 0), App.Vector(0, z1, 0)]
    for i in range(4):
        wall_sketch.addGeometry(Part.LineSegment(wpts[i], wpts[(i + 1) % 4]), False)
    wall = body.newObject("PartDesign::Pad", "WallPad")
    wall.Profile = wall_sketch
    wall.Length = FLANGE_WIDTH_MM
    wall.Midplane = True
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    for hole_x in HOLE_POSITIONS_X_MM:
        hole_sketch.addGeometry(Part.Circle(
            App.Vector(hole_x, 0, 0), App.Vector(0, 0, 1),
            HOLE_DIAMETER_MM / 2), False)
    holes = body.newObject("PartDesign::Pocket", "MountingHoles")
    holes.Profile = hole_sketch
    holes.Type = "ThroughAll"
    doc.recompute()

    tip = body.Tip
    names = []
    for name in helper.vertical_edges(tip.Shape):  # noqa: F821
        points = helper.edge_points(tip.Shape, name)  # noqa: F821
        (px, py, pz), (qx, qy, qz) = points
        if (abs(px - WALL_THICKNESS_MM) < 1e-6
                and abs(py - FLANGE_WIDTH_MM / 2) < 1e-6
                and abs(pz - z0) < 1e-6 and abs(qz - z1) < 1e-6):
            names.append(name)
    helper.assert_count(names, 1, "outer vertical wall edge")  # noqa: F821
    chamfer = body.newObject("PartDesign::Chamfer", "WallChamfer")
    chamfer.Base = (tip, names)
    chamfer.Size = CHAMFER_SIZE_MM
    doc.recompute()

    return body
'''

STEPPED_SHAFT = '''"""Stepped revolved shaft.

Units: millimetres. The profile is revolved 360 degrees about the global Z
axis.
"""

LARGE_DIAMETER_MM = 30.0
LARGE_LENGTH_MM = 20.0
SMALL_DIAMETER_MM = 16.0
SMALL_LENGTH_MM = 30.0


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    profile = body.newObject("Sketcher::SketchObject", "ProfileSketch")
    profile.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    r1 = LARGE_DIAMETER_MM / 2
    r2 = SMALL_DIAMETER_MM / 2
    z1 = LARGE_LENGTH_MM
    z2 = LARGE_LENGTH_MM + SMALL_LENGTH_MM
    pts = [App.Vector(0, 0, 0), App.Vector(r1, 0, 0),
           App.Vector(r1, z1, 0), App.Vector(r2, z1, 0),
           App.Vector(r2, z2, 0), App.Vector(0, z2, 0)]
    for i in range(len(pts)):
        profile.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % len(pts)]), False)

    revolution = body.newObject("PartDesign::Revolution", "Revolution")
    revolution.Profile = profile
    revolution.ReferenceAxis = (profile, ["V_Axis"])
    revolution.Angle = 360.0
    doc.recompute()

    return body
'''


def _build(tmp_path: Path, part_id: str, source: str) -> Path:
    """Build one part in the real CAD and return the exported STEP file."""
    if not LOCAL_CONFIG.is_file():
        pytest.skip("the local FreeCAD configuration is not on this machine")
    project = tmp_path / "project"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / f"{part_id}.py").write_text(source, encoding="utf-8")
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())
    request = BuildRequest(
        project_root=str(project), part_id=part_id,
        language="python-freecad", outputs=("step",), timeout_s=180)
    result = runner.build(request)
    assert result.status == "ok", result.error_text
    return project / result.artifacts["step"]


@pytest.mark.freecad
def test_the_bossed_plate_measures_as_calculated(tmp_path):
    """A boss, a blind pocket and a through-hole in one body."""
    model = load_step(_build(tmp_path, "bossed_plate", BOSSED_PLATE))
    # 100 x 60 x 8 plate = 48000
    # + d24 boss 12 high = 1728 * pi
    # - d10 hole through 20 = 500 * pi
    # - 20 x 20 pocket 4 deep = 1600
    expected = 48000.0 + 1728.0 * math.pi - 500.0 * math.pi - 1600.0
    assert model.is_valid
    assert model.is_single_solid
    assert model.volume == pytest.approx(expected, abs=VOLUME_TOLERANCE_MM3)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx(
        (100.0, 60.0, 20.0), abs=SIZE_TOLERANCE_MM)
    holes = find_holes(model)
    assert len(holes) == 1
    assert holes[0].diameter == pytest.approx(10.0)
    assert holes[0].x == pytest.approx(0.0, abs=SIZE_TOLERANCE_MM)
    assert holes[0].y == pytest.approx(0.0, abs=SIZE_TOLERANCE_MM)
    assert holes[0].z == pytest.approx(10.0, abs=SIZE_TOLERANCE_MM)
    assert holes[0].through is True


@pytest.mark.freecad
def test_the_l_bracket_measures_as_calculated(tmp_path):
    """An orthogonal wall, two mounting holes and a chamfer in one body."""
    model = load_step(_build(tmp_path, "l_bracket", L_BRACKET))
    # 80 x 50 x 8 flange = 32000
    # + 8 x 50 x 40 wall = 16000
    # - two d6 holes through 8 = 144 * pi
    # - 2 mm chamfer on a 40 mm edge = 80
    expected = 32000.0 + 16000.0 - 144.0 * math.pi - 80.0
    assert model.is_valid
    assert model.is_single_solid
    assert model.volume == pytest.approx(expected, abs=VOLUME_TOLERANCE_MM3)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx(
        (80.0, 50.0, 48.0), abs=SIZE_TOLERANCE_MM)
    holes = find_holes(model)
    assert len(holes) == 2
    assert [hole.diameter for hole in holes] == pytest.approx([6.0, 6.0])
    assert [hole.x for hole in holes] == pytest.approx([25.0, 65.0])
    assert [hole.y for hole in holes] == pytest.approx([0.0, 0.0])
    assert [hole.z for hole in holes] == pytest.approx([4.0, 4.0])
    assert all(hole.through for hole in holes)


@pytest.mark.freecad
def test_the_stepped_shaft_measures_as_calculated(tmp_path):
    """A closed half-profile revolved 360 degrees around the Z axis."""
    model = load_step(_build(tmp_path, "stepped_shaft", STEPPED_SHAFT))
    # d30 x 20 = 4500 * pi
    # + d16 x 30 = 1920 * pi
    expected = 4500.0 * math.pi + 1920.0 * math.pi
    assert model.is_valid
    assert model.is_single_solid
    assert model.volume == pytest.approx(expected, abs=VOLUME_TOLERANCE_MM3)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx(
        (30.0, 30.0, 50.0), abs=SIZE_TOLERANCE_MM)
    assert find_holes(model) == []
