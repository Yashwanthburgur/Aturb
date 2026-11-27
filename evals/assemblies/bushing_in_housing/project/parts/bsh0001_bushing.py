"""BSH0001 Flanged bushing with a through bore.

Units: millimetres. The barrel spans Z = 0 to BARREL_LENGTH_MM and the flange
spans Z = BARREL_LENGTH_MM to BARREL_LENGTH_MM + FLANGE_LENGTH_MM.
"""

# --- PARAMS ---
BARREL_DIAMETER_MM = 30.0
BARREL_LENGTH_MM = 20.5
FLANGE_DIAMETER_MM = 44.0
FLANGE_LENGTH_MM = 6.0
BORE_DIAMETER_MM = 16.0
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    profile = body.newObject("Sketcher::SketchObject", "ProfileSketch")
    profile.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    barrel_r = BARREL_DIAMETER_MM / 2
    flange_r = FLANGE_DIAMETER_MM / 2
    z1 = BARREL_LENGTH_MM
    z2 = BARREL_LENGTH_MM + FLANGE_LENGTH_MM
    points = [App.Vector(0, 0, 0), App.Vector(barrel_r, 0, 0),
              App.Vector(barrel_r, z1, 0), App.Vector(flange_r, z1, 0),
              App.Vector(flange_r, z2, 0), App.Vector(0, z2, 0)]
    for index in range(len(points)):
        profile.addGeometry(
            Part.LineSegment(points[index], points[(index + 1) % len(points)]), False)

    revolution = body.newObject("PartDesign::Revolution", "Revolution")
    revolution.Profile = profile
    revolution.ReferenceAxis = (profile, ["V_Axis"])
    revolution.Angle = 360.0
    doc.recompute()

    bore = body.newObject("Sketcher::SketchObject", "BoreSketch")
    bore.Placement = App.Placement(App.Vector(0, 0, z2), App.Rotation())
    bore.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BORE_DIAMETER_MM / 2), False)
    hole = body.newObject("PartDesign::Pocket", "ThroughBore")
    hole.Profile = bore
    hole.Type = "ThroughAll"
    doc.recompute()

    return body
