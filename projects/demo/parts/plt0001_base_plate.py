"""PLT0001 Base plate.

Rectangular plate with two through-holes.
Units: millimetres. Plate is centred on the origin in X and Y; it spans Z = 0 to THICKNESS_MM.
"""

# --- PARAMS ---
LENGTH_MM = 120.0      # along X
WIDTH_MM = 60.0        # along Y
THICKNESS_MM = 5.0     # along Z
HOLE_DIA_MM = 10.0     # diameter of both holes
HOLE_PITCH_MM = 80.0   # centre-to-centre distance of the holes, along X
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
    sk = _rect_sketch(body, "PlateSketch", LENGTH_MM, WIDTH_MM)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = THICKNESS_MM

    # Two through-holes (T1.21)
    hs = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hs.Placement = App.Placement(App.Vector(
        0, 0, THICKNESS_MM), App.Rotation())
    for x in (-HOLE_PITCH_MM / 2, HOLE_PITCH_MM / 2):
        hs.addGeometry(Part.Circle(App.Vector(x, 0, 0),
                       App.Vector(0, 0, 1), HOLE_DIA_MM / 2), False)
    pocket = body.newObject("PartDesign::Pocket", "Holes")
    pocket.Profile = hs
    pocket.Type = "ThroughAll"

    return body
