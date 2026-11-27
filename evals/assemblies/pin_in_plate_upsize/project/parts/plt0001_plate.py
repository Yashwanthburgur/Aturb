"""PLT0001 Mounting plate with a central through-hole.

Units: millimetres. The plate is centred on the origin in X and Y and spans
Z = 0 to PLATE_THICKNESS_MM.
"""

# --- PARAMS ---
PLATE_LENGTH_MM = 100.0
PLATE_WIDTH_MM = 60.0
PLATE_THICKNESS_MM = 10.0
BORE_DIAMETER_MM = 20.4
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    outline = body.newObject("Sketcher::SketchObject", "OutlineSketch")
    half_x = PLATE_LENGTH_MM / 2
    half_y = PLATE_WIDTH_MM / 2
    corners = [App.Vector(-half_x, -half_y, 0), App.Vector(half_x, -half_y, 0),
               App.Vector(half_x, half_y, 0), App.Vector(-half_x, half_y, 0)]
    for index in range(4):
        outline.addGeometry(
            Part.LineSegment(corners[index], corners[(index + 1) % 4]), False)
    pad = body.newObject("PartDesign::Pad", "PlatePad")
    pad.Profile = outline
    pad.Length = PLATE_THICKNESS_MM
    doc.recompute()

    bore = body.newObject("Sketcher::SketchObject", "BoreSketch")
    bore.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM), App.Rotation())
    bore.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BORE_DIAMETER_MM / 2), False)
    hole = body.newObject("PartDesign::Pocket", "CentralBore")
    hole.Profile = bore
    hole.Type = "ThroughAll"
    doc.recompute()

    return body
