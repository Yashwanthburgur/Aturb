# build123d — verified API

Verified against build123d 0.13.0 on 2026-11-11, installed with Python 3.12 via `uv add build123d pyyaml`.
All rows below were executed on this machine; nothing is copied from upstream documentation.
Re-verify after any version bump in `pyproject.toml`.

| Call                                       | Purpose                                    | Verified output                                                         |
| ------------------------------------------ | ------------------------------------------ | ----------------------------------------------------------------------- |
| `Box(10, 10, 10)`                          | Create a 10 x 10 x 10 box                  | `volume = 999.9999999999998`, `is_valid = True`                         |
| `Cylinder(radius, height)`                 | Create a cylinder solid                    | `Cylinder(5, 20)` -> volume `1570.7963267948965` (pi*r^2*h)             |
| `Box(10, 10, 10).center()`                 | Centre of mass point                       | `Pos(3, 0, 0) * box` -> `Vector: (X=18, Y=0, Z=0)`                      |
| `shape.locate(Location((15, 0, 0)))`       | Position geometry by translation           | `located.center()` -> `Vector: (X=15, Y=0, Z=0)`                        |
| `shape.moved(Location((0,0,0), (0,0,45)))` | Position geometry by rotation              | `rotated.bounding_box().size` -> `Vector: (X=14.1421, Y=14.1421, Z=10)` |
| `box - cyl`                                | Subtract one solid from another (operator) | `1000 - 392.699` overlap cut -> volume `803.650459`, `is_valid = True`  |
| `box.cut(cyl)`                             | Subtract one solid from another (method)   | volume `803.650459`                                                     |
| `export_step(shape, path)`                 | Export a solid to STEP                     | returns `True`, file written and present on disk                        |
| `import_step(path)`                        | Import a STEP file                         | returns `Solid`, `solids()` length `1`, volume `999.9999999999998`      |
| `shape.volume`                             | Read volume                                | `Box(10, 10, 10)` -> `999.9999999999998`                                |
| `shape.bounding_box()`                     | Read bounding box                          | `BoundBox: bbox: -5.0 <= x <= 5.0, -5.0 <= y <= 5.0, -5.0 <= z <= 5.0`  |
| `BoundBox.size`                            | Read bounding-box dimensions               | `Vector: (X=10, Y=10, Z=10)`                                            |
| `shape.is_valid`                           | Check geometry validity                    | `True`                                                                  |

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
