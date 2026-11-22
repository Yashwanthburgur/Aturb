"""PLT0002 Base plate with filleted corners.

Rectangular plate with two through-holes and a fillet on the four vertical
corner edges.
Units: millimetres. Plate is centred on the origin in X and Y; it spans Z = 0 to THICKNESS_MM.
"""

# --- PARAMS ---
LENGTH_MM = 120.0        # along X
WIDTH_MM = 60.0          # along Y
THICKNESS_MM = 5.0       # along Z
HOLE_DIA_MM = 10.0       # diameter of both holes
HOLE_PITCH_MM = 80.0     # centre-to-centre distance of the holes, along X
FILLET_RADIUS_MM = 3.0   # radius of the fillet on the four vertical corner edges
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
    doc.recompute()

    # The four vertical corner edges are selected by their geometry, never by
    # an assumed index (ADR-0007). The helper only selects and asserts; the
    # fillet feature is created here. The harness injects the helper into the
    # namespace of this file, so a static reader cannot see the name.
    corner_names = helper.corner_edges(body.Tip.Shape, LENGTH_MM, WIDTH_MM)  # noqa: F821
    helper.assert_count(corner_names, 4, "vertical corner edges")  # noqa: F821
    fillet = body.newObject("PartDesign::Fillet", "CornerFillet")
    fillet.Base = (pad, corner_names)
    fillet.Radius = FILLET_RADIUS_MM
    doc.recompute()

    # Two through-holes (T1.21), cut after the fillet (T1.25)
    hs = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hs.Placement = App.Placement(App.Vector(
        0, 0, THICKNESS_MM), App.Rotation())
    for x in (-HOLE_PITCH_MM / 2, HOLE_PITCH_MM / 2):
        hs.addGeometry(Part.Circle(App.Vector(x, 0, 0),
                       App.Vector(0, 0, 1), HOLE_DIA_MM / 2), False)
    pocket = body.newObject("PartDesign::Pocket", "Holes")
    pocket.Profile = hs
    pocket.Type = "ThroughAll"
    doc.recompute()

    return body
