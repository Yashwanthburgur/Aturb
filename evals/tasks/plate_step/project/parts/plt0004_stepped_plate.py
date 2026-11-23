"""PLT0004 Stepped plate with boss corner fillets and two through-holes.

Units: millimetres. The base and boss are centred on the origin in X and Y;
the base spans Z = 0 to BASE_THICKNESS_MM and the boss rises above it.
"""

# --- PARAMS ---
BASE_LENGTH_MM = 120.0
BASE_WIDTH_MM = 60.0
BASE_THICKNESS_MM = 5.0
BOSS_LENGTH_MM = 60.0
BOSS_WIDTH_MM = 60.0
BOSS_HEIGHT_MM = 3.0
FILLET_RADIUS_MM = 4.0
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
    base_sketch = _rect_sketch(
        body, "BaseSketch", BASE_LENGTH_MM, BASE_WIDTH_MM)
    base = body.newObject("PartDesign::Pad", "BasePad")
    base.Profile = base_sketch
    base.Length = BASE_THICKNESS_MM
    doc.recompute()

    boss_sketch = _rect_sketch(
        body, "BossSketch", BOSS_LENGTH_MM, BOSS_WIDTH_MM)
    boss_sketch.Placement = App.Placement(
        App.Vector(0, 0, BASE_THICKNESS_MM), App.Rotation())
    boss = body.newObject("PartDesign::Pad", "BossPad")
    boss.Profile = boss_sketch
    boss.Length = BOSS_HEIGHT_MM
    doc.recompute()

    # Select the four vertical boss corners by geometry, never by edge index.
    corner_names = helper.corner_edges(  # noqa: F821
        boss.Shape, BOSS_LENGTH_MM, BOSS_WIDTH_MM)
    helper.assert_count(corner_names, 4, "vertical boss corner edges")  # noqa: F821
    fillet = body.newObject("PartDesign::Fillet", "BossCornerFillet")
    fillet.Base = (boss, corner_names)
    fillet.Radius = FILLET_RADIUS_MM
    doc.recompute()

    hole_sketch = body.newObject("Sketcher::SketchObject", "HoleSketch")
    hole_sketch.Placement = App.Placement(App.Vector(
        0, 0, BASE_THICKNESS_MM + BOSS_HEIGHT_MM), App.Rotation())
    for x in (-HOLE_PITCH_MM / 2, HOLE_PITCH_MM / 2):
        hole_sketch.addGeometry(Part.Circle(
            App.Vector(x, 0, 0), App.Vector(0, 0, 1), HOLE_DIA_MM / 2), False)
    holes = body.newObject("PartDesign::Pocket", "Holes")
    holes.Profile = hole_sketch
    holes.Type = "ThroughAll"
    doc.recompute()

    return body
