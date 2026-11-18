"""Broken part: Pad on an empty sketch (should fail to recompute)."""

import FreeCAD as App
import Part


def build(doc):
    """Build a body with an empty-sketch Pad."""
    body = doc.addObject("PartDesign::Body", "Body")

    # Sketch with NO geometry
    sketch = body.newObject("Sketcher::SketchObject", "EmptySketch")

    # Pad whose Profile references the empty sketch
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10.0

    return body
