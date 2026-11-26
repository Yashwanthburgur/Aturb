"""PLT0005 Bossed plate with a blind pocket and a concentric through-hole.

Units: millimetres. The plate is centred on the origin in X and Y.
"""

# --- PARAMS ---
PLATE_LENGTH_MM = 100.0
PLATE_WIDTH_MM = 60.0
PLATE_THICKNESS_MM = 8.0
BOSS_DIAMETER_MM = 24.0
BOSS_HEIGHT_MM = 12.0
HOLE_DIAMETER_MM = 10.0
POCKET_LENGTH_MM = 20.0
POCKET_WIDTH_MM = 20.0
POCKET_DEPTH_MM = 4.0
POCKET_CENTRE_X_MM = 32.0
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    def _rect(body, name, length, width, cx=0.0, cy=0.0):
        sk = body.newObject("Sketcher::SketchObject", name)
        x, y = length / 2, width / 2
        pts = [App.Vector(cx - x, cy - y, 0), App.Vector(cx + x, cy - y, 0),
               App.Vector(cx + x, cy + y, 0), App.Vector(cx - x, cy + y, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
        return sk

    body = doc.addObject("PartDesign::Body", "Body")

    plate = body.newObject("PartDesign::Pad", "PlatePad")
    plate.Profile = _rect(body, "PlateSketch", PLATE_LENGTH_MM, PLATE_WIDTH_MM)
    plate.Length = PLATE_THICKNESS_MM
    doc.recompute()

    pocket_sketch = _rect(body, "PocketSketch", POCKET_LENGTH_MM,
                          POCKET_WIDTH_MM, POCKET_CENTRE_X_MM)
    pocket_sketch.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM), App.Rotation())
    pocket = body.newObject("PartDesign::Pocket", "BlindPocket")
    pocket.Profile = pocket_sketch
    pocket.Type = "Length"
    pocket.Length = POCKET_DEPTH_MM
    doc.recompute()

    boss_sketch = body.newObject("Sketcher::SketchObject", "BossSketch")
    boss_sketch.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM), App.Rotation())
    boss_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BOSS_DIAMETER_MM / 2), False)
    boss = body.newObject("PartDesign::Pad", "BossPad")
    boss.Profile = boss_sketch
    boss.Length = BOSS_HEIGHT_MM
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM + BOSS_HEIGHT_MM), App.Rotation())
    hole_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), HOLE_DIAMETER_MM / 2), False)
    hole = body.newObject("PartDesign::Pocket", "ThroughHole")
    hole.Profile = hole_sketch
    hole.Type = "ThroughAll"
    doc.recompute()

    return body
