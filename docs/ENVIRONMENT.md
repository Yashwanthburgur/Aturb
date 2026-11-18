# Environment

## Operating system

Not yet verified.

## Tools (git, uv, Python)

Not yet verified.

## FreeCAD

FreeCAD version: 1.0.1 (build 39285 Git, 2025-05-14).

Path pattern of the command-line executable:

`C:\Program Files\FreeCAD <version>\bin\freecadcmd.exe`

It was found by listing the `FreeCAD*` folders under `C:\Program Files` and then
searching each one recursively for a file matching `*cmd*.exe`. The executable name
differs between FreeCAD versions, so the search is the reliable step, not a fixed name.

## Running FreeCAD headless

Command form that worked (from the repository root):

`uv run python tools/spikes/run_fc.py tools/spikes/fc_hello.py`

which runs the configured executable with the script path as its only argument, e.g.
`"C:/Program Files/FreeCAD 1.0/bin/freecadcmd.exe" <absolute path to the script>`.

The process exits on its own (verified in T1.10: `EXIT: 0`, no hang, no timeout). The
script's own `print` output arrives on stdout. `freecadcmd.exe` also writes its banner
(`FreeCAD 1.0.1, Libs: ...`) to stdout before the script output; stdout is otherwise
empty of surprises and stderr is empty.

## Passing data into FreeCAD scripts

Works: the script path goes on the command line; all other data goes in environment
variables. The pattern verified in T1.11 is a JSON request file whose absolute path is
passed in `ATURB_REQUEST`, read inside the script with `os.environ["ATURB_REQUEST"]` and
then opened as UTF-8. Command used:

`uv run python tools/spikes/run_fc.py tools/spikes/fc_args.py --env ATURB_REQUEST=<absolute path to sample_request.json>`

Observed: `EXIT: 0`, then
`REQUEST_PATH: <absolute path>` and `REQUEST_JSON: {'hello': 'world'}`.

Notes:

- `run_fc.py --env KEY=VALUE` copies the current environment and adds the pair, so the
  child sees it normally.
- The value must already be an absolute path when it reaches `run_fc.py`. `$PWD` in the
  card's example is PowerShell syntax and is not expanded by `cmd.exe`, so on this machine
  the absolute path was written out in full.
- No separate `--` argument channel is used; everything beyond the script path is shell
  quoting, which is why the environment variable is the transport.

## Exit codes and error output

An exception in a script does **not** change the exit code. Verified in T1.12 with
`tools/spikes/fc_raise.py` (contents: `raise RuntimeError("planted failure")`):

- Observed exit code: **0** (`EXIT: 0`), identical to a script that succeeds.
- `planted failure` appeared in **STDERR only**, not in stdout.
- The stderr text is a single line, not a Python traceback:

  `Exception while processing file: <absolute script path> [planted failure]`

- stdout contained only the usual FreeCAD banner.

Consequence for the harness: the exit code cannot be trusted to mean "the build
worked". Success must be judged from a result that the script itself writes out, and the
stderr line is the only evidence an exception happened.

## Timeouts and killing processes

Not yet verified.

## PartDesign headless findings

**T1.24 — Determinism spike**: Two builds of `projects/demo/parts/plt0001_base_plate.py` into separate output directories (`out1/` and `out2/`). Both builds completed successfully (RESULT status "ok"). Both STEP files measured with build123d (import_step, solid.volume, solid.area, solid.faces(), solid.bounding_box().size).

Measurements:

| Metric             | Build 1      | Build 2      | Difference | Expected  | Tolerance | Within tol? |
| ------------------ | ------------ | ------------ | ---------- | --------- | --------- | ----------- |
| Volume (mm³)       | 35214.601837 | 35214.601837 | 0.000000   | 35214.602 | 0.01      | ✅          |
| Surface area (mm²) | 16200.0      | 16200.0      | 0.0        | —         | 0.01      | ✅          |
| BBox X (mm)        | 120.000000   | 120.000000   | 0.000000   | 120       | 0.01      | ✅          |
| BBox Y (mm)        | 60.000000    | 60.000000    | 0.000000   | 60        | 0.01      | ✅          |
| BBox Z (mm)        | 5.000000     | 5.000000     | 0.000000   | 5         | 0.01      | ✅          |
| Face count         | 8            | 8            | 0          | —         | 0         | ✅          |
| is_valid           | True         | True         | —          | —         | —         | ✅          |

Conclusion: **Two builds identical: yes**. Volume, surface area, all three bounding-box dimensions, and face count agree exactly (differences 0.0) within the 0.01 mm tolerance.

> Note: The STEP files contain identical geometry. All measurements used calls already verified in docs/api_notes/build123d.md (import_step, solid.volume, solid.area, solid.faces(), solid.bounding_box().size, solid.is_valid).

**T1.26 — Hole vs Pocket spike**: Tested `PartDesign::Hole` feature for simple through-holes in the demo plate.

Hole feature properties verified via `dir()` (T1.26):

- `Diameter` (Base.Quantity, default 6.0 mm)
- `Depth` (Base.Quantity, default 25.0 mm)
- `DepthType` (str, enum: "Dimension", "ThroughAll", "ToLast", "UpToFace", "UpToShape", "TwoSided")
- `Profile` (accepts face reference tuple `(feature, "FaceN")` or sketch)
- `Refine` (bool, default True)
- `Tapered` (bool, default False)
- Other thread-related properties (ThreadType, ThreadSize, etc.) not used.

Build attempts:

1.  Hole with sketch Profile (`hole1.Profile = hs`): **Failed** — "Linked shape object is empty"
2.  Hole with face reference Profile (`hole1.Profile = (pad, "Face6")`), Diameter=10, DepthType="ThroughAll": **Builds OK** but **does not cut holes** (volume remains 36000 mm³, same as solid plate).
3.  Single Hole with two circles in sketch: **Same result** — builds OK, volume 36000 mm³.

For comparison, `PartDesign::Pocket` with same sketch cuts correctly: volume 35607.3 mm³ (one hole) → 35214.6 mm³ (two holes).

Measured Hole volume: **36000.000 mm³** (no material removed).
Expected volume (with holes): **35214.602 mm³**.

Recommendation: **Use Pocket for simple through-holes**. Hole feature does not cut material in headless FreeCAD 1.0.1 with the tested configurations.

## STEP export

Method that worked (T1.17): call `exportStep` on the shape of the object that `build(doc)`
returned, passing the full output path:

`obj.Shape.exportStep("<out dir>/<stem>.step")`

- `hasattr(box.Shape, "exportStep")` is `True` on FreeCAD 1.0.1; the signature is
  `exportStep(filename)`. The format flags are optional.
- It **returns `None`**, not a boolean, so the return value cannot be used to detect
  failure. The spike checks `os.path.isfile(...)` and `os.path.getsize(...) > 0` instead,
  and raises if either fails.
- FreeCAD writes a "Statistics on Transfer (Write)" banner plus
  `Step File Name : ...(170 ents)  Write Done` to stdout. That banner is normal output,
  not an error.
- The exported box STEP was 6854 bytes, and the FCStd saved alongside it 2417 bytes. Both
  non-zero is the acceptance check used in T1.17.
- Export happens after `doc.saveAs`, so the native file never depends on the export
  succeeding.

## Paths with spaces

Not yet verified.
