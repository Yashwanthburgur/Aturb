# FreeCAD pack — agent prompt

You write one part file for the FreeCAD pack. This file is the whole contract
between you and the pack.

## File contract

- One Python file, with the `.py` extension.
- It defines one function, `build(doc)`, and returns the final object of the
  part. The runner imports the file inside FreeCAD, calls `build(doc)` with a
  fresh document, recomputes the document and exports the STEP file of the
  object you returned.
- The document is given to you. Do not create another one, do not save it and
  do not export a STEP file: the runner saves the document (T1.16) and exports
  the STEP file (T1.17).
- The only imports you may use are `FreeCAD`, `Part`, `PartDesign`, `Sketcher`
  and `math`. You may not read or write files, and you may not use `open`,
  `exec`, `eval`, `compile` or `__import__`.
- All lengths are in millimetres.
- Put the dimensions of the part in named constants at the top of the file.

## Verified API calls you may use

Every call below was executed and recorded in
[`docs/api_notes/freecad.md`](../../docs/api_notes/freecad.md). The task ID is
the row that verified it.

| Call                                                                              | Purpose                               | Verified in task |
| --------------------------------------------------------------------------------- | ------------------------------------- | ---------------- |
| `doc.addObject("Part::Box", "Box")`                                               | Add a primitive to the document       | T1.16            |
| `doc.recompute()`                                                                 | Recompute the document after a change | T1.16            |
| `body.newObject("PartDesign::Body", "Body")`                                      | Create a PartDesign Body              | T1.20            |
| `sk.addGeometry(Part.LineSegment(p1, p2), False)`                                 | Add a line to a sketch                | T1.20            |
| `body.newObject("PartDesign::Pad", "Pad")`                                        | Create a Pad feature                  | T1.20            |
| `pad.Profile = sketch`                                                            | Set the profile of a Pad              | T1.20            |
| `pad.Length = value`                                                              | Set the length of a Pad               | T1.20            |
| `body.newObject("Sketcher::SketchObject", name)`                                  | Create a sketch inside a Body         | T1.21            |
| `sk.Placement = App.Placement(App.Vector(x, y, z), App.Rotation())`               | Place a sketch                        | T1.21            |
| `sk.addGeometry(Part.Circle(center, normal, radius), False)`                      | Add a circle to a sketch              | T1.21            |
| `body.newObject("PartDesign::Pocket", "Holes")`                                   | Create a Pocket feature               | T1.21            |
| `pocket.Profile = sketch`                                                         | Set the profile of a Pocket           | T1.21            |
| `pocket.Type = "ThroughAll"`                                                      | Cut through the whole material        | T1.21            |
| `obj.isValid()`                                                                   | Check that a feature is valid         | T1.23            |
| `body.Tip`                                                                        | Reach the last feature of a Body      | T1.25            |
| `obj.Shape.Edges`                                                                 | Enumerate the edges of a solid        | T1.25            |
| `body.newObject("PartDesign::Fillet", "Fillet")`                                  | Create a fillet                       | T1.25            |
| `fillet.Base = (feature, ["Edge1", "Edge2"])`                                     | Choose the edges to fillet            | T1.25            |
| `fillet.Radius = value`                                                           | Set the radius of a fillet            | T1.25            |
| `body.newObject("PartDesign::Pocket", "Holes")` with `pocket.Type = "ThroughAll"` | Cut through-holes                     | T1.26            |

Use `PartDesign::Pocket` for through-holes. `PartDesign::Hole` does not cut
material in headless FreeCAD 1.0.1 (T1.26).

## Output contract

Reply with the content of the file and nothing else. No explanation, no
summary and no text around it.
