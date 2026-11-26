"""SHF0001 Stepped revolved shaft.

Units: millimetres. The profile is revolved 360 degrees about the global Z
axis.
"""

# --- PARAMS ---
LARGE_DIAMETER_MM = 30.0
LARGE_LENGTH_MM = 20.0
SMALL_DIAMETER_MM = 16.0
SMALL_LENGTH_MM = 30.0
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    profile = body.newObject("Sketcher::SketchObject", "ProfileSketch")
    profile.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    r1 = LARGE_DIAMETER_MM / 2
    r2 = SMALL_DIAMETER_MM / 2
    z1 = LARGE_LENGTH_MM
    z2 = LARGE_LENGTH_MM + SMALL_LENGTH_MM
    pts = [App.Vector(0, 0, 0), App.Vector(r1, 0, 0),
           App.Vector(r1, z1, 0), App.Vector(r2, z1, 0),
           App.Vector(r2, z2, 0), App.Vector(0, z2, 0)]
    for i in range(len(pts)):
        profile.addGeometry(Part.LineSegment(
            pts[i], pts[(i + 1) % len(pts)]), False)

    revolution = body.newObject("PartDesign::Revolution", "Revolution")
    revolution.Profile = profile
    revolution.ReferenceAxis = (profile, ["V_Axis"])
    revolution.Angle = 360.0
    doc.recompute()

    return body
