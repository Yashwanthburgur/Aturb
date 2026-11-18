"""Hole spike: demo plate with PartDesign::Hole feature instead of Pocket."""

import FreeCAD as App
import Part


# --- PARAMS (copied from plt0001_base_plate.py) ---
LENGTH_MM = 120.0       # along X
WIDTH_MM = 60.0         # along Y
THICKNESS_MM = 5.0      # along Z
HOLE_DIA_MM = 10.0      # diameter of both holes
HOLE_PITCH_MM = 80.0    # centre-to-centre distance of the holes, along X
# --- END PARAMS ---


def build(doc):
    """Build the part with a single Hole feature (two circles in sketch) instead of Pocket."""
    def _rect_sketch(body, name, length, width):
        sk = body.newObject("Sketcher::SketchObject", name)
        x, y = length / 2, width / 2
        pts = [App.Vector(-x, -y, 0), App.Vector(x, -y, 0),
               App.Vector(x, y, 0), App.Vector(-x, y, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
        return sk

    body = doc.addObject("PartDesign::Body", "Body")

    # Base plate
    sk = _rect_sketch(body, "PlateSketch", LENGTH_MM, WIDTH_MM)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = THICKNESS_MM

    doc.recompute()

    # Hole sketch on top face (Z = THICKNESS_MM) with two circles
    hs = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hs.Placement = App.Placement(App.Vector(
        0, 0, THICKNESS_MM), App.Rotation())
    for x in (-HOLE_PITCH_MM / 2, HOLE_PITCH_MM / 2):
        hs.addGeometry(Part.Circle(App.Vector(x, 0, 0),
                       App.Vector(0, 0, 1), HOLE_DIA_MM / 2), False)

    # Single Hole feature using the sketch with two circles
    # Per implementation guide: Profile = the circle sketch
    hole = body.newObject("PartDesign::Hole", "Holes")
    hole.Profile = hs
    hole.Diameter = HOLE_DIA_MM
    hole.DepthType = "ThroughAll"

    doc.recompute()

    return body
