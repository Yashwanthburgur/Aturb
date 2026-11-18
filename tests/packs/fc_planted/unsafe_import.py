import os

import FreeCAD as App
import Part


def build(doc):
    box = doc.addObject("Part::Box", "Box")
    box.Length = 10
    box.Width = 10
    box.Height = 10
    doc.recompute()
    return box
