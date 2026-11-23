"""PLT0003 Base plate with a centred rectangular pocket and two through-holes.

Units: millimetres. The plate is centred on the origin in X and Y and spans
Z = 0 to THICKNESS_MM; the pocket opens at the top and leaves a floor.
"""

# --- PARAMS ---
LENGTH_MM = 120.0
WIDTH_MM = 60.0
THICKNESS_MM = 10.0
POCKET_LENGTH_MM = 40.0
POCKET_WIDTH_MM = 20.0
POCKET_DEPTH_MM = 4.0
HOLE_DIA_MM = 10.0
HOLE_PITCH_MM = 80.0
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    def _rect_sketch(body, name, length, width):
        sk = body.newObject("Sketcher::SketchObject", name)
        x, y = length / 2, width / 2
        pts = [App.Vector(-x, -y, 0), App.Vector(x, -y, 0),
               App.Vector(x, y, 0), App.Vector(-x, y, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
        return sk

    body = doc.addObject("PartDesign::Body", "Body")
    plate_sketch = _rect_sketch(body, "PlateSketch", LENGTH_MM, WIDTH_MM)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = plate_sketch
    pad.Length = THICKNESS_MM
    doc.recompute()

    pocket_sketch = _rect_sketch(
        body, "PocketSketch", POCKET_LENGTH_MM, POCKET_WIDTH_MM)
    pocket_sketch.Placement = App.Placement(
        App.Vector(0, 0, THICKNESS_MM), App.Rotation())
    pocket = body.newObject("PartDesign::Pocket", "RectangularPocket")
    pocket.Profile = pocket_sketch
    pocket.Length = POCKET_DEPTH_MM
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.Placement = App.Placement(
        App.Vector(0, 0, THICKNESS_MM), App.Rotation())
    for x in (-HOLE_PITCH_MM / 2, HOLE_PITCH_MM / 2):
        hole_sketch.addGeometry(Part.Circle(
            App.Vector(x, 0, 0), App.Vector(0, 0, 1), HOLE_DIA_MM / 2), False)
    holes = body.newObject("PartDesign::Pocket", "Holes")
    holes.Profile = hole_sketch
    holes.Type = "ThroughAll"
    doc.recompute()

    return body
