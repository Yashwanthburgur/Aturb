"""BRK0001 L-bracket with an orthogonal wall, mounting holes and a chamfer.

Units: millimetres. The flange spans X = 0 to FLANGE_LENGTH_MM and the wall
stands on it at X = 0 to WALL_THICKNESS_MM.
"""

# --- PARAMS ---
FLANGE_LENGTH_MM = 80.0
FLANGE_WIDTH_MM = 50.0
FLANGE_THICKNESS_MM = 8.0
WALL_THICKNESS_MM = 8.0
WALL_HEIGHT_MM = 40.0
HOLE_DIAMETER_MM = 6.0
HOLE_POSITIONS_X_MM = (25.0, 65.0)
CHAMFER_SIZE_MM = 2.0
# --- END PARAMS ---


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
        flange_sketch.addGeometry(Part.LineSegment(
            pts[i], pts[(i + 1) % 4]), False)
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
        wall_sketch.addGeometry(Part.LineSegment(
            wpts[i], wpts[(i + 1) % 4]), False)
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
