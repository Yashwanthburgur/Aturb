import FreeCAD as App
import Part


def build(doc):
    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    pad = doc.addObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10
    doc.recompute()
    return pad
