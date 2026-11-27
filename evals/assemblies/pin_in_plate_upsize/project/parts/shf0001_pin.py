"""SHF0001 Shoulder pin: a shaft with a wider flange on top of it.

Units: millimetres. The shaft spans Z = 0 to SHAFT_LENGTH_MM and the flange
spans Z = SHAFT_LENGTH_MM to SHAFT_LENGTH_MM + FLANGE_LENGTH_MM.
"""

# --- PARAMS ---
SHAFT_DIAMETER_MM = 20.0
SHAFT_LENGTH_MM = 15.5
FLANGE_DIAMETER_MM = 36.0
FLANGE_LENGTH_MM = 8.0
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    profile = body.newObject("Sketcher::SketchObject", "ProfileSketch")
    profile.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    shaft_r = SHAFT_DIAMETER_MM / 2
    flange_r = FLANGE_DIAMETER_MM / 2
    z1 = SHAFT_LENGTH_MM
    z2 = SHAFT_LENGTH_MM + FLANGE_LENGTH_MM
    points = [App.Vector(0, 0, 0), App.Vector(shaft_r, 0, 0),
              App.Vector(shaft_r, z1, 0), App.Vector(flange_r, z1, 0),
              App.Vector(flange_r, z2, 0), App.Vector(0, z2, 0)]
    for index in range(len(points)):
        profile.addGeometry(
            Part.LineSegment(points[index], points[(index + 1) % len(points)]), False)

    revolution = body.newObject("PartDesign::Revolution", "Revolution")
    revolution.Profile = profile
    revolution.ReferenceAxis = (profile, ["V_Axis"])
    revolution.Angle = 360.0
    doc.recompute()

    return body
