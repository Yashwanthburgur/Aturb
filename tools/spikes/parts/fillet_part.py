"""Fillet spike: demo plate with 3.0 mm fillet on four vertical corner edges."""

import FreeCAD as App
import Part

# --- PARAMS (copied from plt0001_base_plate.py) ---
LENGTH_MM = 120.0       # along X
WIDTH_MM = 60.0         # along Y
THICKNESS_MM = 5.0      # along Z
HOLE_DIA_MM = 10.0      # diameter of both holes
HOLE_PITCH_MM = 80.0    # centre-to-centre distance of the holes, along X
FILLET_RADIUS_MM = 3.0  # starting default
# --- END PARAMS ---


def build(doc):
    """Build the part with filleted corners (fillet applied before holes)."""
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

    # Find vertical corner edges on the Pad (before holes)
    edges = pad.Shape.Edges
    corner_edge_names = []

    corner_x = LENGTH_MM / 2
    corner_y = WIDTH_MM / 2

    for idx, edge in enumerate(edges):
        verts = edge.Vertexes
        if len(verts) != 2:
            continue  # skip circular edges which have 1 vertex
        v1, v2 = verts[0], verts[1]

        # Check if vertical: same X, same Y, different Z (within 1e-6)
        if (abs(v1.X - v2.X) <= 1e-6 and
            abs(v1.Y - v2.Y) <= 1e-6 and
                abs(v1.Z - v2.Z) > 1e-6):
            # Check if at a corner: X = ±60, Y = ±30
            x = v1.X  # same as v2.X
            y = v1.Y  # same as v2.Y
            if (abs(abs(x) - corner_x) <= 1e-6 and
                    abs(abs(y) - corner_y) <= 1e-6):
                # Edge name format: "Edge" + str(index + 1)
                corner_edge_names.append(f"Edge{idx + 1}")

    if len(corner_edge_names) != 4:
        raise RuntimeError(
            f"Expected exactly 4 vertical corner edges, found {len(corner_edge_names)}: "
            f"{corner_edge_names}. Total edges: {len(edges)}"
        )

    print(f"Selected fillet edges: {corner_edge_names}")

    # Create PartDesign::Fillet with Base = (pad, [edge_names])
    # The fillet must be applied to the Pad feature before holes are added.
    fillet = body.newObject("PartDesign::Fillet", "CornerFillet")
    fillet.Base = (pad, corner_edge_names)
    fillet.Radius = FILLET_RADIUS_MM

    doc.recompute()

    # Two through-holes (added after fillet)
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
