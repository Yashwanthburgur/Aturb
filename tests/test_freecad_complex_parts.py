"""Complex mechanical parts, built in the real CAD and measured neutrally.

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

RIBBED_BRACKET = '''"""Ribbed L-bracket with a triangular gusset rib and two mounting holes.

Units: millimetres. The flange spans X = 0 to FLANGE_LENGTH_MM and the wall
stands on it at X = 0 to WALL_THICKNESS_MM.
"""

FLANGE_LENGTH_MM = 80.0
FLANGE_WIDTH_MM = 50.0
FLANGE_THICKNESS_MM = 8.0
WALL_THICKNESS_MM = 8.0
WALL_HEIGHT_MM = 40.0
RIB_RUN_MM = 30.0
RIB_HEIGHT_MM = 30.0
RIB_THICKNESS_MM = 8.0
HOLE_DIAMETER_MM = 6.0
HOLE_POSITIONS_MM = ((60.0, -15.0), (60.0, 15.0))


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

    rib_sketch = body.newObject("Sketcher::SketchObject", "RibSketch")
    rib_sketch.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    rpts = [App.Vector(WALL_THICKNESS_MM, z0, 0),
            App.Vector(WALL_THICKNESS_MM + RIB_RUN_MM, z0, 0),
            App.Vector(WALL_THICKNESS_MM, z0 + RIB_HEIGHT_MM, 0)]
    for i in range(3):
        rib_sketch.addGeometry(Part.LineSegment(rpts[i], rpts[(i + 1) % 3]), False)
    rib = body.newObject("PartDesign::Pad", "RibPad")
    rib.Profile = rib_sketch
    rib.Length = RIB_THICKNESS_MM
    rib.Midplane = True
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    for hole_x, hole_y in HOLE_POSITIONS_MM:
        hole_sketch.addGeometry(Part.Circle(
            App.Vector(hole_x, hole_y, 0), App.Vector(0, 0, 1),
            HOLE_DIAMETER_MM / 2), False)
    holes = body.newObject("PartDesign::Pocket", "MountingHoles")
    holes.Profile = hole_sketch
    holes.Type = "ThroughAll"
    doc.recompute()

    return body
'''

FLANGED_HUB = '''"""Flanged hub with a bolt circle and a stepped central bore.

Units: millimetres. The flange and the hub are centred on the origin in X and Y.
The through-bore is cut before the counterbore; the other order gives the same
solid.
"""

FLANGE_DIAMETER_MM = 80.0
FLANGE_THICKNESS_MM = 10.0
HUB_DIAMETER_MM = 40.0
HUB_HEIGHT_MM = 20.0
COUNTERBORE_DIAMETER_MM = 24.0
COUNTERBORE_DEPTH_MM = 8.0
BORE_DIAMETER_MM = 14.0
BOLT_HOLE_DIAMETER_MM = 6.0
BOLT_CIRCLE_RADIUS_MM = 30.0
BOLT_HOLE_COUNT = 4


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part
    import math

    body = doc.addObject("PartDesign::Body", "Body")

    flange_sketch = body.newObject("Sketcher::SketchObject", "FlangeSketch")
    flange_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), FLANGE_DIAMETER_MM / 2), False)
    flange = body.newObject("PartDesign::Pad", "FlangePad")
    flange.Profile = flange_sketch
    flange.Length = FLANGE_THICKNESS_MM
    doc.recompute()

    hub_sketch = body.newObject("Sketcher::SketchObject", "HubSketch")
    hub_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    hub_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), HUB_DIAMETER_MM / 2), False)
    hub = body.newObject("PartDesign::Pad", "HubPad")
    hub.Profile = hub_sketch
    hub.Length = HUB_HEIGHT_MM
    doc.recompute()

    bolt_sketch = body.newObject("Sketcher::SketchObject", "BoltHoleSketch")
    bolt_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    for index in range(BOLT_HOLE_COUNT):
        angle = 2.0 * math.pi * index / BOLT_HOLE_COUNT
        bolt_sketch.addGeometry(Part.Circle(
            App.Vector(BOLT_CIRCLE_RADIUS_MM * math.cos(angle),
                       BOLT_CIRCLE_RADIUS_MM * math.sin(angle), 0),
            App.Vector(0, 0, 1), BOLT_HOLE_DIAMETER_MM / 2), False)
    bolt_holes = body.newObject("PartDesign::Pocket", "BoltHoles")
    bolt_holes.Profile = bolt_sketch
    bolt_holes.Type = "ThroughAll"
    doc.recompute()

    top_z = FLANGE_THICKNESS_MM + HUB_HEIGHT_MM

    bore_sketch = body.newObject("Sketcher::SketchObject", "BoreSketch")
    bore_sketch.Placement = App.Placement(App.Vector(0, 0, top_z), App.Rotation())
    bore_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BORE_DIAMETER_MM / 2), False)
    bore = body.newObject("PartDesign::Pocket", "CentralBore")
    bore.Profile = bore_sketch
    bore.Type = "ThroughAll"
    doc.recompute()

    cbore_sketch = body.newObject("Sketcher::SketchObject", "CounterboreSketch")
    cbore_sketch.Placement = App.Placement(App.Vector(0, 0, top_z), App.Rotation())
    cbore_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), COUNTERBORE_DIAMETER_MM / 2), False)
    cbore = body.newObject("PartDesign::Pocket", "Counterbore")
    cbore.Profile = cbore_sketch
    cbore.Type = "Length"
    cbore.Length = COUNTERBORE_DEPTH_MM
    doc.recompute()

    return body
'''

ENCLOSURE = '''"""Hollow enclosure with outer corner fillets, a blind cavity and floor holes.

Units: millimetres. The box is centred on the origin in X and Y. The outer
corner fillets are cut before the interior cavity; the other order gives the
same solid.
"""

BOX_LENGTH_MM = 100.0
BOX_WIDTH_MM = 70.0
BOX_HEIGHT_MM = 30.0
CORNER_FILLET_RADIUS_MM = 6.0
CAVITY_LENGTH_MM = 84.0
CAVITY_WIDTH_MM = 54.0
CAVITY_DEPTH_MM = 24.0
FLOOR_THICKNESS_MM = 6.0
FLOOR_HOLE_DIAMETER_MM = 5.0
FLOOR_HOLE_POSITIONS_MM = ((32.0, 18.0), (32.0, -18.0),
                            (-32.0, 18.0), (-32.0, -18.0))


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    box_sketch = body.newObject("Sketcher::SketchObject", "BoxSketch")
    hx = BOX_LENGTH_MM / 2
    hy = BOX_WIDTH_MM / 2
    pts = [App.Vector(-hx, -hy, 0), App.Vector(hx, -hy, 0),
           App.Vector(hx, hy, 0), App.Vector(-hx, hy, 0)]
    for i in range(4):
        box_sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
    box = body.newObject("PartDesign::Pad", "BoxPad")
    box.Profile = box_sketch
    box.Length = BOX_HEIGHT_MM
    doc.recompute()

    edges = helper.corner_edges(box.Shape, BOX_LENGTH_MM, BOX_WIDTH_MM)  # noqa: F821
    helper.assert_count(edges, 4, "outer vertical corner edges")  # noqa: F821
    fillet = body.newObject("PartDesign::Fillet", "CornerFillet")
    fillet.Base = (box, edges)
    fillet.Radius = CORNER_FILLET_RADIUS_MM
    doc.recompute()

    cavity_sketch = body.newObject("Sketcher::SketchObject", "CavitySketch")
    cavity_sketch.Placement = App.Placement(
        App.Vector(0, 0, BOX_HEIGHT_MM), App.Rotation())
    cx = CAVITY_LENGTH_MM / 2
    cy = CAVITY_WIDTH_MM / 2
    cpts = [App.Vector(-cx, -cy, 0), App.Vector(cx, -cy, 0),
            App.Vector(cx, cy, 0), App.Vector(-cx, cy, 0)]
    for i in range(4):
        cavity_sketch.addGeometry(Part.LineSegment(cpts[i], cpts[(i + 1) % 4]), False)
    cavity = body.newObject("PartDesign::Pocket", "Cavity")
    cavity.Profile = cavity_sketch
    cavity.Type = "Length"
    cavity.Length = CAVITY_DEPTH_MM
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "FloorHoleSketch")
    hole_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLOOR_THICKNESS_MM), App.Rotation())
    for hole_x, hole_y in FLOOR_HOLE_POSITIONS_MM:
        hole_sketch.addGeometry(Part.Circle(
            App.Vector(hole_x, hole_y, 0), App.Vector(0, 0, 1),
            FLOOR_HOLE_DIAMETER_MM / 2), False)
    holes = body.newObject("PartDesign::Pocket", "FloorHoles")
    holes.Profile = hole_sketch
    holes.Type = "ThroughAll"
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
def test_the_ribbed_l_bracket_measures_as_calculated(tmp_path):
    """A flange, a wall, a triangular rib and two mounting holes in one body."""
    model = load_step(_build(tmp_path, "ribbed_l_bracket", RIBBED_BRACKET))
    # 80 x 50 x 8 flange = 32000
    # + 8 x 50 x 40 wall = 16000
    # + 30 x 30 / 2 x 8 rib = 3600
    # - two d6 holes through 8 = 144 * pi
    expected = 32000.0 + 16000.0 + 3600.0 - 144.0 * math.pi
    assert model.is_valid
    assert model.is_single_solid
    assert model.volume == pytest.approx(expected, abs=VOLUME_TOLERANCE_MM3)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx(
        (80.0, 50.0, 48.0), abs=SIZE_TOLERANCE_MM)
    holes = find_holes(model)
    assert len(holes) == 2
    assert [hole.diameter for hole in holes] == pytest.approx([6.0, 6.0])
    assert [hole.x for hole in holes] == pytest.approx([60.0, 60.0])
    assert [hole.y for hole in holes] == pytest.approx([-15.0, 15.0])
    assert [hole.z for hole in holes] == pytest.approx([4.0, 4.0])
    assert all(hole.through for hole in holes)


@pytest.mark.freecad
def test_the_flanged_hub_measures_as_calculated(tmp_path):
    """A flange, a hub, a bolt circle and a stepped bore in one body."""
    model = load_step(_build(tmp_path, "flanged_hub", FLANGED_HUB))
    # d80 x 10 flange = 16000 * pi
    # + d40 x 20 hub = 8000 * pi
    # - d24 counterbore 8 deep = 1152 * pi
    # - d14 bore through the remaining 22 = 1078 * pi
    # - four d6 bolt holes through 10 = 360 * pi
    expected = 21410.0 * math.pi
    assert model.is_valid
    assert model.is_single_solid
    assert model.volume == pytest.approx(expected, abs=VOLUME_TOLERANCE_MM3)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx(
        (80.0, 80.0, 30.0), abs=SIZE_TOLERANCE_MM)
    holes = find_holes(model)
    # The blind counterbore is a hole of its own, and its axis is clear of
    # material because the coaxial through-bore runs through it.
    assert len(holes) == 6
    assert [hole.diameter for hole in holes] == pytest.approx(
        [6.0, 6.0, 14.0, 24.0, 6.0, 6.0])
    assert [hole.x for hole in holes] == pytest.approx(
        [-30.0, 0.0, 0.0, 0.0, 0.0, 30.0], abs=SIZE_TOLERANCE_MM)
    assert [hole.y for hole in holes] == pytest.approx(
        [0.0, -30.0, 0.0, 0.0, 30.0, 0.0], abs=SIZE_TOLERANCE_MM)
    assert [hole.z for hole in holes] == pytest.approx(
        [5.0, 5.0, 11.0, 26.0, 5.0, 5.0], abs=SIZE_TOLERANCE_MM)
    assert all(hole.through for hole in holes)


@pytest.mark.freecad
def test_the_hollow_enclosure_measures_as_calculated(tmp_path):
    """A box, four outer fillets, a blind cavity and four floor holes."""
    model = load_step(_build(tmp_path, "hollow_enclosure", ENCLOSURE))
    # 100 x 70 x 30 box = 210000
    # - four corner fillets of r6 over 30 = 4 * (36 - 9 * pi) * 30
    # - 84 x 54 x 24 cavity = 108864
    # - four d5 holes through the 6 floor = 150 * pi
    expected = (210000.0 - 4 * (36.0 - 9.0 * math.pi) * 30.0
                - 108864.0 - 150.0 * math.pi)
    assert model.is_valid
    assert model.is_single_solid
    assert model.volume == pytest.approx(expected, abs=VOLUME_TOLERANCE_MM3)
    size = model.bbox_size
    assert (size.X, size.Y, size.Z) == pytest.approx(
        (100.0, 70.0, 30.0), abs=SIZE_TOLERANCE_MM)
    holes = find_holes(model)
    assert len(holes) == 4
    assert [hole.diameter for hole in holes] == pytest.approx([5.0] * 4)
    assert [hole.x for hole in holes] == pytest.approx(
        [-32.0, -32.0, 32.0, 32.0])
    assert [hole.y for hole in holes] == pytest.approx(
        [-18.0, 18.0, -18.0, 18.0])
    assert [hole.z for hole in holes] == pytest.approx([3.0] * 4)
    assert all(hole.through for hole in holes)
