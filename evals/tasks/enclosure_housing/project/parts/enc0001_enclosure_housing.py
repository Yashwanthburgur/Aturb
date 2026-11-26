"""ENC0001 Hollow enclosure with outer corner fillets, a blind cavity and floor holes.

Units: millimetres. The box is centred on the origin in X and Y. The outer
corner fillets are cut before the interior cavity; the other order gives the
same solid.
"""

# --- PARAMS ---
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
# --- END PARAMS ---


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
        box_sketch.addGeometry(Part.LineSegment(
            pts[i], pts[(i + 1) % 4]), False)
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
        cavity_sketch.addGeometry(Part.LineSegment(
            cpts[i], cpts[(i + 1) % 4]), False)
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
