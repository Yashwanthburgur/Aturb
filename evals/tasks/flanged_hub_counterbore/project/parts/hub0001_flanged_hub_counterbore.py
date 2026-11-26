"""HUB0001 Flanged hub with a bolt circle and a stepped central bore.

Units: millimetres. The flange and the hub are centred on the origin in X and Y.
The through-bore is cut before the counterbore; the other order gives the same
solid.
"""

# --- PARAMS ---
FLANGE_DIAMETER_MM = 80.0
FLANGE_THICKNESS_MM = 10.0
HUB_DIAMETER_MM = 40.0
HUB_HEIGHT_MM = 20.0
COUNTERBORE_DIAMETER_MM = 24.0
COUNTERBORE_DEPTH_MM = 8.0
BORE_DIAMETER_MM = 14.0
BOLT_HOLE_DIAMETER_MM = 6.0
BOLT_CIRCLE_RADIUS_MM = 30.0
BOLT_HOLE_COUNT = 4
# --- END PARAMS ---


def build(doc):
    """Build the part in the given document and return the final object."""
    import math

    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    flange_sketch = body.newObject("Sketcher::SketchObject", "FlangeSketch")
    flange_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), FLANGE_DIAMETER_MM / 2), False)
    flange = body.newObject("PartDesign::Pad", "FlangePad")
    flange.Profile = flange_sketch
    flange.Length = FLANGE_THICKNESS_MM
    doc.recompute()

    hub_sketch = body.newObject("Sketcher::SketchObject", "HubSketch")
    hub_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    hub_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), HUB_DIAMETER_MM / 2), False)
    hub = body.newObject("PartDesign::Pad", "HubPad")
    hub.Profile = hub_sketch
    hub.Length = HUB_HEIGHT_MM
    doc.recompute()

    bolt_sketch = body.newObject("Sketcher::SketchObject", "BoltHoleSketch")
    bolt_sketch.Placement = App.Placement(
        App.Vector(0, 0, FLANGE_THICKNESS_MM), App.Rotation())
    for index in range(BOLT_HOLE_COUNT):
        angle = 2.0 * math.pi * index / BOLT_HOLE_COUNT
        bolt_sketch.addGeometry(Part.Circle(
            App.Vector(BOLT_CIRCLE_RADIUS_MM * math.cos(angle),
                       BOLT_CIRCLE_RADIUS_MM * math.sin(angle), 0),
            App.Vector(0, 0, 1), BOLT_HOLE_DIAMETER_MM / 2), False)
    bolt_holes = body.newObject("PartDesign::Pocket", "BoltHoles")
    bolt_holes.Profile = bolt_sketch
    bolt_holes.Type = "ThroughAll"
    doc.recompute()

    top_z = FLANGE_THICKNESS_MM + HUB_HEIGHT_MM

    bore_sketch = body.newObject("Sketcher::SketchObject", "BoreSketch")
    bore_sketch.Placement = App.Placement(
        App.Vector(0, 0, top_z), App.Rotation())
    bore_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BORE_DIAMETER_MM / 2), False)
    bore = body.newObject("PartDesign::Pocket", "CentralBore")
    bore.Profile = bore_sketch
    bore.Type = "ThroughAll"
    doc.recompute()

    cbore_sketch = body.newObject(
        "Sketcher::SketchObject", "CounterboreSketch")
    cbore_sketch.Placement = App.Placement(
        App.Vector(0, 0, top_z), App.Rotation())
    cbore_sketch.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), COUNTERBORE_DIAMETER_MM / 2), False)
    cbore = body.newObject("PartDesign::Pocket", "Counterbore")
    cbore.Profile = cbore_sketch
    cbore.Type = "Length"
    cbore.Length = COUNTERBORE_DEPTH_MM
    doc.recompute()

    return body
