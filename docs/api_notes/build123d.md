# build123d — verified API

Verified against build123d 0.13.0 on 2026-11-11, installed with Python 3.12 via `uv add build123d pyyaml`.
All rows below were executed on this machine; nothing is copied from upstream documentation.
Re-verify after any version bump in `pyproject.toml`.
The STEP inspection rows were added on 2026-11-19 by the Phase 3 spike
`tools/spikes/b3d_inspect.py`; run that script to reproduce them.
The hole-detection rows were verified in-session on 2026-11-19 against the same
fixture; they are the calls that `aturb/verify/holes.py` uses.
The engineering-measurement rows were verified in-session on 2026-11-26 against
the same fixture; they are the calls that `aturb/verify/engineering.py` uses.

| Call                                             | Purpose                                    | Verified output                                                                                      |
| ------------------------------------------------ | ------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `Box(10, 10, 10)`                                | Create a 10 x 10 x 10 box                  | `volume = 999.9999999999998`, `is_valid = True`                                                      |
| `Cylinder(radius, height)`                       | Create a cylinder solid                    | `Cylinder(5, 20)` -> volume `1570.7963267948965` (pi*r^2*h)                                          |
| `Box(10, 10, 10).center()`                       | Centre of mass point                       | `Pos(3, 0, 0) * box` -> `Vector: (X=18, Y=0, Z=0)`                                                   |
| `shape.locate(Location((15, 0, 0)))`             | Position geometry by translation           | `located.center()` -> `Vector: (X=15, Y=0, Z=0)`                                                     |
| `shape.moved(Location((0,0,0), (0,0,45)))`       | Position geometry by rotation              | `rotated.bounding_box().size` -> `Vector: (X=14.1421, Y=14.1421, Z=10)`                              |
| `box - cyl`                                      | Subtract one solid from another (operator) | `1000 - 392.699` overlap cut -> volume `803.650459`, `is_valid = True`                               |
| `box.cut(cyl)`                                   | Subtract one solid from another (method)   | volume `803.650459`                                                                                  |
| `Cylinder(5, 5).locate(Location((x, 0, 0)))`     | Position a cylinder at a given X           | `locate(Location((-40, 0, 0)))` -> `center()` = `Vector: (X=-40, Y=0, Z=0)`                          |
| `Box(120, 60, 5)` minus two positioned cylinders | Plate with two through-holes               | volume `35214.60183660256`, bbox `Vector: (X=120, Y=60, Z=5)`                                        |
| `export_step(shape, path)`                       | Export a solid to STEP                     | returns `True`, file written and present on disk                                                     |
| `import_step(path)`                              | Import a STEP file                         | returns `Solid`, `solids()` length `1`, volume `999.9999999999998`                                   |
| `shape.volume`                                   | Read volume                                | `Box(10, 10, 10)` -> `999.9999999999998`                                                             |
| `shape.bounding_box()`                           | Read bounding box                          | `BoundBox: bbox: -5.0 <= x <= 5.0, -5.0 <= y <= 5.0, -5.0 <= z <= 5.0`                               |
| `BoundBox.size`                                  | Read bounding-box dimensions               | `Vector: (X=10, Y=10, Z=10)`                                                                         |
| `shape.is_valid`                                 | Check geometry validity                    | `True`                                                                                               |
| `shape.solids()`                                 | List the solids inside a shape             | On the plate fixture: `1`. On a two-solid STEP: `2`                                                  |
| `shape.faces()`                                  | List the faces of a shape                  | On the plate fixture: `8` (6 planes, 2 cylinders)                                                    |
| `shape.edges()`                                  | List the edges of a shape                  | On the plate fixture: `18` (4 circular, the rest straight)                                           |
| `shape.area`                                     | Read surface area                          | Plate fixture: `16200.000000000022`                                                                  |
| `face.geom_type`                                 | Classify a face by surface type            | `GeomType.PLANE` (6 faces) and `GeomType.CYLINDER` (2 faces) on the fixture                          |
| `face.radius`                                    | Radius of a cylindrical face               | `5.0` for both hole faces of the fixture                                                             |
| `face.center(CenterOf.MASS)`                     | Centre of a cylindrical face, on its axis  | `(-39.99999999999967, 5.73e-17, -1.24e-16)` for the hole at X = -40                                  |
| `face.center()`                                  | Default centre of a face (GEOMETRY)        | `(-45.0, -1.03e-12, 0.0)` for the hole at X = -40 — **not** the hole axis                            |
| `face.axis_of_rotation`                          | Axis of a cylindrical face                 | `Axis: (position=(-40, 0, -2.5), direction=(0, 0, 1))`                                               |
| `face.edges()`                                   | Edges bounding one face                    | A through-hole cylinder has 3 edges, 2 of them circular                                              |
| `edge.geom_type`                                 | Classify an edge by curve type             | `GeomType.CIRCLE` for the 4 hole edges of the fixture                                                |
| `edge.radius`                                    | Radius of a circular edge                  | `5.0` for all 4 hole edges                                                                           |
| `edge.arc_center`                                | True centre of a circular edge             | `(-40, 0, 2.5)`, `(40, 0, 2.5)`, `(-40, 0, -2.5)`, `(40, 0, -2.5)`                                   |
| `edge.center()`                                  | Default centre of an edge (GEOMETRY)       | `(-45.0, 6.12e-16, 2.5)` for the circle centred at `(-40, 0, 2.5)`                                   |
| `shape.distance_to(other)`                       | Minimum distance between two shapes        | `15.0` for two 10 mm boxes 25 mm apart; `0.0` when they overlap                                      |
| `shape.closest_points(other)`                    | Closest point pair between two shapes      | `(Vector(5, -5, 5), Vector(20, -5, 5))` for the 15 mm gap                                            |
| `shape.distance_to_with_closest_points(other)`   | Distance and its closest point pair        | `(15.0, Vector(5, -5, 5), Vector(20, -5, 5))`                                                        |
| `a & b`                                          | Intersection of two shapes                 | Overlapping boxes: `Part`, volume `499.9999999999999`; disjoint: `Compound`, volume `0`, 0 solids    |
| `a.intersect(b)`                                 | Intersection as a list                     | Overlapping: `ShapeList` of length 1, `listed[0].volume` = `499.9999999999999`; disjoint: `None`     |
| `Compound([...])` + `export_step(...)`           | Write several solids into one STEP file    | Two 10 mm boxes 30 mm apart -> one STEP file                                                         |
| `import_step(path)` on a multi-solid STEP        | Read a STEP file holding several solids    | Returns `Compound`; `solids()` = 2, volumes `[1000.0, 1000.0]`, total `1999.9999999999995`, 12 faces |
| `edge.start_point()`                             | Start point of an edge                     | `Vector: (X=-35, Y=0, Z=2.5)` for the seam edge of the hole face at X = -40                          |
| `edge.length`                                    | Length of an edge                          | `31.41592653589793` for a hole circle (2*pi*5); `5.0` for the seam line of the hole face             |
| `face.normal_at(point)`                          | Normal of a face at a point                | `Vector: (X=-1, Y=0, Z=0)` on the hole face at X = -40 — it points towards the axis                  |
| `face.bounding_box()`                            | Bounding box of one face                   | `min` = `Vector: (X=-45, Y=-5, Z=-2.5)`, `max` = `Vector: (X=-35, Y=5, Z=2.5)` for the hole face     |
| `Edge.make_line(p1, p2)`                         | A straight edge between two points         | returns an `Edge`; `length` = `268.51443164195103` for a line spanning the model diagonal            |
| `shape & line`                                   | Intersection of a solid with a line        | On the hole axis: `None` (no material). Through the plate: an `Edge` of length `5.0`                 |
| `Vector(x, y, z)`                                | Build a point                              | `Vector: (X=1, Y=2, Z=3)`                                                                            |
| `a - b` (two vectors)                            | Offset between two points                  | `Vector: (X=5, Y=0, Z=5)` for the start point of the hole face at X = -40 minus its axis position    |
| `vector.dot(other)`                              | Dot product of two vectors                 | `5.0` for that offset against the axis direction `(0, 0, 1)`                                         |
| `vector.length`                                  | Length of a vector                         | `7.0710678118654755` for that offset                                                                 |
| `shape.bounding_box().min` and `.max`            | The two corners of the bounding box        | Plate fixture: `min` = `Vector: (X=-60, Y=-30, Z=-2.5)`, `max` = `Vector: (X=60, Y=30, Z=2.5)`       |
| `solid.center(CenterOf.MASS)`                    | Mass centroid of a solid                   | Asymmetric L: `Vector: (X=-0.714286, Y=-0.357143, Z=-0.357143)`                                      |
| `solid.center()`                                 | Default centre of a solid (MASS)           | Same as `CenterOf.MASS`: `Vector: (X=-0.714286, Y=-0.357143, Z=-0.357143)`                           |
| `solid.center(CenterOf.BOUNDING_BOX)`            | Middle of the bounding box of a solid      | Asymmetric L: `Vector: (X=0, Y=0, Z=0)` — not the mass centre                                        |
| `solid.center(CenterOf.GEOMETRY)`                | Geometric centre of a solid                | Raises `ValueError: Center of GEOMETRY is not supported for this object`                             |
| `compound.center(CenterOf.MASS)`                 | Mass centroid of several solids            | Three 10 mm boxes: `Vector: (X=-3.33333, Y=3.33333, Z=0)`                                            |

## Notes from verification

- `bounding_box` is a **method**: call it as `shape.bounding_box()`. Passing `tolerance` and
  `optimal` is optional and defaults to `optimal=True`.
- `is_valid` is a **property**: read it as `shape.is_valid`, not `shape.is_valid()`.
  `is_manifold` is also a property and also returned `True` for a box.
- `volume` and `center` are accessed without parentheses on `Shape` (`shape.volume`,
  `shape.center()`); `solids()` and `bounding_box()` are methods.
- The transfer function names are `export_step` and `import_step`. `build123d.ExportSTEP`
  does not exist in 0.13.0 and raises `AttributeError`.
- `Builder` is abstract in 0.13.0 and cannot be instantiated; use `BuildPart`, `BuildLine`
  or `BuildSketch` for a context-manager style build.
- `import_step` returned a `Solid` for a single-solid STEP file (not a `Compound`), despite
  the annotation claiming `Compound`.
- Subtraction is geometric: a cylinder that overhangs the box removes only the shared material,
  which is why `box - cyl` (803.65) is larger than the naive difference of the two volumes.
- `face.center()` and `edge.center()` default to `CenterOf.GEOMETRY`, which is **wrong** for a
  cylinder or a circle: the hole at X = -40 reported `(-45, 0, 0)` and its circle reported
  `(-45, 0, 2.5)`. Use `face.center(CenterOf.MASS)` and `edge.arc_center` instead.
- `CenterOf.MASS` on the hole axis returned `(-39.99999999999967, 5.73e-17, -1.24e-16)`, so
  positions carry floating-point noise and must be compared with a tolerance.
- `Shape.intersect()` returns a `ShapeList` (which has no `volume`) for overlapping shapes and
  `None` for disjoint ones. Use the `&` operator, which always returns a shape.
- `distance_to` returns `0.0` for overlapping solids, so a zero distance means touching or
  overlapping, never "far apart".
- `import_step` returns a `Solid` for a single-solid STEP and a `Compound` for a multi-solid
  STEP. Always read `shape.solids()` rather than assuming the top-level type.
- A cylindrical face's area is `2 * pi * r * h`, so its height is `area / (2 * pi * r)`.
  The fixture's hole faces measured `157.0796326795` for r = 5 and h = 5.
- `face.normal_at(point)` points away from the material of a solid, so on a hole it points
  towards the cylinder axis. A void gives `normal.dot(axis.position - point) > 0` (`5.0` on
  the fixture); a boss gives a negative value.
- `shape & line` answers `None` when the line meets no material and an `Edge` when it crosses
  material, so the length of the returned edge says how much material the line crossed.
- `Edge.make_line` makes a finite edge, so the line has to be long enough to leave the model
  on both sides.
- `face.bounding_box()` gives `min` and `max` as `Vector` objects, not as tuples.
- The seam edge of a cylinder starts on the axis, so a point that is clearly off the axis has
  to be found by trying the edges of the face.
- `Vector.length` and `Vector.dot` measure an offset vector, and `a - b` gives the offset
  between two points.
- `center` on a solid or a compound defaults to `CenterOf.MASS`, unlike `face.center()` and
  `edge.center()`, which default to `CenterOf.GEOMETRY`. The signature is
  `center(self, center_of: CenterOf = CenterOf.MASS) -> Vector`.
- `CenterOf.GEOMETRY` raises `ValueError: Center of GEOMETRY is not supported for this object`
  on a solid, so a solid centre must always ask for `MASS` or `BOUNDING_BOX`.
- `center` lives on the 3D mixin and not on the base `Shape` class: `hasattr(build123d.Shape,
"center")` is `False`, while `Solid` and `Compound` have it. Read the centroid from
  `shape.solids()` when the static type of the shape is `Shape`.
- `bounding_box().min` and `bounding_box().max` are `Vector` objects, like
  `bounding_box().size`.
