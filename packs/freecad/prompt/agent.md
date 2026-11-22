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
[`docs/api_notes/freecad.md`](../../../docs/api_notes/freecad.md). The task ID
is the row that verified it.

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
| `fillet.Base = (feature, names)`                                                  | Choose the edges to fillet            | T1.25            |
| `fillet.Radius = value`                                                           | Set the radius of a fillet            | T1.25            |
| `body.newObject("PartDesign::Pocket", "Holes")` with `pocket.Type = "ThroughAll"` | Cut through-holes                     | T1.26            |

Use `PartDesign::Pocket` for through-holes. `PartDesign::Hole` does not cut
material in headless FreeCAD 1.0.1 (T1.26).

The names you pass to `fillet.Base` come from the selection helper below, not
from a position you assume.

## The selection helper

The harness puts a selection helper into your file under the global name
`helper`. It is already there when `build(doc)` runs, so do not import it and
do not try to load it from a file: an import of it is refused by the static
check.

The helper selects, measures and asserts. It never creates a feature, never
changes the feature tree and never performs the engineering operation. You
still create the feature and set its parameters yourself.

Selection is by geometric property — orientation, vertex coordinates,
geometric type, radius and position — and never by an assumed positional
index. The helper returns the names the CAD gives the geometry, such as
`"Edge3"` or `"Face5"`, counted from the shape you pass in. Select on the
shape of the feature that will consume the names, so the names and the feature
agree.

### Calls the helper offers

| Call                                                              | Purpose                                                   | Verified in task |
| ----------------------------------------------------------------- | --------------------------------------------------------- | ---------------- |
| `helper.vertical_edges(shape)`                                    | names of the edges that run along Z                       | T1.25            |
| `helper.corner_edges(shape, length_mm, width_mm)`                 | names of the vertical edges at the corners                | T1.25            |
| `helper.circular_edges(shape, radius_mm, tolerance_mm=...)`       | names of the closed circular edges of a radius            | T1.25            |
| `helper.edge_type(shape, name)`                                   | type of an edge: circle, line or other                    | T1.25            |
| `helper.edge_length(shape, name)`                                 | length of an edge in millimetres                          | T1.25            |
| `helper.edge_points(shape, name)`                                 | vertex coordinates of an edge                             | T1.25            |
| `helper.faces_by_normal(shape, nx, ny, nz, tolerance=...)`        | names of the flat faces with an outward normal            | T6.06a           |
| `helper.top_faces(shape)`                                         | names of the flat faces that face up                      | T6.06a           |
| `helper.bottom_faces(shape)`                                      | names of the flat faces that face down                    | T6.06a           |
| `helper.cylindrical_faces(shape, radius_mm, tolerance_mm=...)`    | names of the round faces of a radius                      | T6.06a           |
| `helper.face_normal(shape, name)`                                 | outward unit normal of a face                             | T6.06a           |
| `helper.face_area(shape, name)`                                   | area of a face                                            | T6.06a           |
| `helper.face_center(shape, name)`                                 | centre of mass of a face                                  | T6.06a           |
| `helper.assert_count(items, expected, label)`                     | raise when the count is not the expected one              | T1.25            |
| `helper.assert_radius(shape, names, radius_mm, tolerance_mm=...)` | raise when a selected edge is not a circle of that radius | T1.25            |

The task ID is the row of
[`docs/api_notes/freecad.md`](../../../docs/api_notes/freecad.md) that verified
the FreeCAD call behind the helper call. The helper itself reaches your file
through the harness (T6.05).

### Using the helper

The helper gives you the names; you write the feature.

```python
edges = helper.corner_edges(pad.Shape, LENGTH_MM, WIDTH_MM)
helper.assert_count(edges, 4, "vertical corner edges")

fillet = body.newObject("PartDesign::Fillet", "Fillet")
fillet.Base = (pad, edges)
fillet.Radius = FILLET_RADIUS_MM
```

`LENGTH_MM`, `WIDTH_MM` and `FILLET_RADIUS_MM` are your own constants, and
`pad` is the feature whose shape you selected on.

## Output contract

Reply with the content of the file and nothing else. No explanation, no
summary and no text around it.
