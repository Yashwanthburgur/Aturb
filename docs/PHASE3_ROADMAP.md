# Phase 3 task roadmap — neutral checks on STEP

Draft task cards for Phase 3, derived from the verified API notes
([`docs/api_notes/build123d.md`](api_notes/build123d.md),
[`docs/api_notes/freecad.md`](api_notes/freecad.md)) and the Phase 3 technical
handoff. The orchestrator's Part 2 guide stays authoritative if it differs from
this draft.

Scope: a neutral verification layer that judges exported STEP geometry with
build123d, independently of the CAD backend. Phase 4 (task set and scoring) is
out of scope here.

Rules every card inherits:

- Correctness is judged from exported STEP only, never from CAD-native
  diagnostics ([`docs/adr/0005-checks-on-step.md`](adr/0005-checks-on-step.md)).
- The core stays CAD-neutral: no CAD brand name or CAD concept inside `aturb/`.
- Only calls recorded in the API notes or verified in-session may be used.
- Files at most 300 lines; each card changes at most about 200 lines.
- Every chosen default is marked `# starting default`.
- No commit; the orchestrator commits.

---

## T3.01 — Spike: verify the build123d inspection calls Phase 3 needs

GOAL: Turn every assumption about build123d 0.13.0 STEP inspection into a
recorded fact, before any verification code is written.

FILES (only these): `tools/spikes/b3d_inspect.py`, `docs/api_notes/build123d.md`

DO EXACTLY:

1. Create `tools/spikes/b3d_inspect.py`. It must run from the repository root
   with `uv run python tools/spikes/b3d_inspect.py` and print one labelled line
   per fact. It inspects the committed fixture
   `packs/stub/fixtures/plate_2holes.step` (120 x 60 x 5 plate, two 10 mm
   through-holes at X = +/-40) and covers: shape type, solid/face/edge counts,
   volume, area, validity, bounding box, face geometry types, cylindrical face
   radius, axis position and direction, circular edge radius and arc centre,
   distance between two solids, closest points, intersection volume, and a
   two-solid STEP written to a temporary folder and read back.
2. Run it and keep the output.
3. Add one row per call that actually ran to the table in
   `docs/api_notes/build123d.md`, with the real output you saw. Add a short
   "Notes from verification" bullet for every trap the run exposed.

DO NOT: record a call the script did not run. Do not add production code.

ACCEPTANCE:

- `uv run python tools/spikes/b3d_inspect.py` runs clean and prints the facts.
- `docs/api_notes/build123d.md` has rows for hole detection, cylindrical faces,
  distance, clearance, intersection and multi-solid STEP handling.
- `uv run ruff check tools/spikes/b3d_inspect.py` -> All checks passed!

---

## T3.02 — Neutral STEP inspection module

GOAL: One place in the core that loads an exported STEP and exposes its neutral
facts, so every later check reads the same model.

FILES (only these): `aturb/verify/__init__.py`, `aturb/verify/step.py`,
`tests/test_verify_step.py`

DO EXACTLY:

1. Create `aturb/verify/step.py` with a frozen dataclass `StepModel` holding
   the imported shape and the path it came from, and a function
   `load_step(path: Path) -> StepModel` that imports the STEP with build123d
   and raises `StepLoadError` when the file is missing or cannot be read.
2. Give `StepModel` read-only properties for `solids`, `faces`, `edges`,
   `volume`, `area`, `is_valid` and `bbox_size`, each backed by a call verified
   in T3.01.
3. Create `tests/test_verify_step.py` using the committed fixture
   `packs/stub/fixtures/plate_2holes.step`: one solid, eight faces, eighteen
   edges, volume 35214.602 within 0.01, area 16200 within 0.01, valid, bounding
   box 120 x 60 x 5 within 0.01. One test for a missing file raising
   `StepLoadError`.

DO NOT: import any CAD module. Do not re-assert the volume, bounding-box or
validity checks that already exist in `tests/test_demo_plate.py`,
`tests/test_spike_box.py` and `tests/test_smoke_build123d.py`; those tests keep
their own assertions.

ACCEPTANCE:

- `uv run pytest tests/test_verify_step.py -q` -> all pass
- `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK
- `uv run python tools/size_limit.py` -> size_limit: OK

---

## T3.03 — Cylindrical face classification

GOAL: Recognise cylindrical faces and describe each one, so holes can be found
without guessing.

FILES (only these): `aturb/verify/cylinders.py`, `tests/test_verify_cylinders.py`

DO EXACTLY:

1. Create `aturb/verify/cylinders.py` with a frozen dataclass `Cylinder`
   (radius, axis_x, axis_y, axis_z, direction_x, direction_y, direction_z,
   height, through) and a function `cylindrical_faces(model: StepModel) ->
list[Cylinder]`.
2. Select faces with `face.geom_type == GeomType.CYLINDER`. Take the radius
   from `face.radius`, the axis from `face.axis_of_rotation`, the height from
   `face.area / (2 * pi * radius)`, and mark a cylinder as through when it has
   two circular edges.
3. Use `face.center(CenterOf.MASS)` for the axis position. The default
   `face.center()` is `CenterOf.GEOMETRY` and is wrong for a cylindrical face;
   record that trap in a comment.
4. Create `tests/test_verify_cylinders.py` against the committed fixture: two
   cylinders, radius 5.0, axes at X = -40 and X = +40, Y = 0, direction (0, 0, 1),
   height 5.0, both through.

ACCEPTANCE:

- `uv run pytest tests/test_verify_cylinders.py -q` -> all pass
- `uv run ruff check .` -> All checks passed!

---

## T3.04 — Hole detection

GOAL: Report the holes of a part from its exported STEP: count, diameter and
position.

FILES (only these): `aturb/verify/holes.py`, `tests/test_verify_holes.py`

DO EXACTLY:

1. Create `aturb/verify/holes.py` with a frozen dataclass `Hole` (diameter,
   x, y, z, through) and a function `find_holes(model: StepModel) -> list[Hole]`
   built on `cylindrical_faces`.
2. Diameter is twice the cylinder radius. Position is the cylinder axis
   position. Sort the result by x, then y, then z, so the order is stable.
3. Create `tests/test_verify_holes.py` against the committed fixture: two holes,
   diameter 10.0, at X = -40 and X = +40, Y = 0, both through.

DO NOT: add a hole-count check to the runner yet; that is T3.09.

ACCEPTANCE:

- `uv run pytest tests/test_verify_holes.py -q` -> all pass

---

## T3.05 — Distance and clearance between solids

GOAL: Measure the gap between two solids, so a clearance check can be written.

FILES (only these): `aturb/verify/clearance.py`, `tests/test_verify_clearance.py`

DO EXACTLY:

1. Create `aturb/verify/clearance.py` with `min_distance(a, b) -> float` using
   `distance_to`, and `clearance_ok(a, b, min_gap: float) -> bool`.
2. `distance_to` returns 0.0 for overlapping solids. Record that in a comment.
3. Create `tests/test_verify_clearance.py` with two boxes built with build123d:
   a 15 mm gap measures 15.0, an overlapping pair measures 0.0, and
   `clearance_ok` is true for a 15 mm gap against a 10 mm minimum and false
   against a 20 mm minimum.

ACCEPTANCE:

- `uv run pytest tests/test_verify_clearance.py -q` -> all pass

---

## T3.06 — Intersection and interference

GOAL: Detect two solids that interfere, from their exported geometry.

FILES (only these): `aturb/verify/interference.py`, `tests/test_verify_interference.py`

DO EXACTLY:

1. Create `aturb/verify/interference.py` with `intersection_volume(a, b) ->
float` and `interferes(a, b, tolerance: float = 0.0) -> bool`.
2. Use the `&` operator for the intersection. `Shape.intersect()` returns a
   `ShapeList` for overlapping shapes and `None` for disjoint ones, so it must
   not be used directly; record that trap in a comment.
3. Create `tests/test_verify_interference.py` with two boxes built with
   build123d: an overlapping pair gives an intersection volume of 500 within
   0.01 and interferes, a disjoint pair gives 0 and does not.

ACCEPTANCE:

- `uv run pytest tests/test_verify_interference.py -q` -> all pass

---

## T3.07 — Multi-solid STEP handling

GOAL: A STEP file may hold several solids. The neutral layer must handle that
without guessing.

FILES (only these): `aturb/verify/step.py`, `tests/test_verify_multisolids.py`

DO EXACTLY:

1. Extend `StepModel` so a multi-solid STEP is reported honestly: `solids`
   returns every solid, and a property `is_single_solid` says whether the file
   holds exactly one.
2. Create `tests/test_verify_multisolids.py`: write a two-solid STEP with
   build123d into `tmp_path`, import it, and assert two solids of volume 1000
   each, `is_single_solid` false, and the total volume 2000 within 0.01.

ACCEPTANCE:

- `uv run pytest tests/test_verify_multisolids.py -q` -> all pass

---

## T3.08 — Neutral check result type

GOAL: One result type for every neutral check, so results can be printed,
stored and compared without a CAD concept anywhere.

FILES (only these): `aturb/verify/result.py`, `tests/contract/test_verify_result.py`

DO EXACTLY:

1. Create `aturb/verify/result.py` with a frozen dataclass `CheckResult`
   (name, passed, expected, actual, tolerance, message) and a `to_dict`.
   `expected` and `actual` are floats or None; `tolerance` is a float.
2. Add a classmethod `from_measurement(name, expected, actual, tolerance)` that
   sets `passed` by comparing the two numbers within the tolerance, and a
   classmethod `failure(name, message)` for a check that could not be measured.
3. Create `tests/contract/test_verify_result.py`: a measurement inside the
   tolerance passes, one outside fails, a failure carries no numbers, and
   `to_dict` returns the six fields.

DO NOT: add a CAD concept, a geometry schema or a JSON geometry format.

ACCEPTANCE:

- `uv run pytest tests/contract/test_verify_result.py -q` -> all pass

---

## T3.09 — Check runner

GOAL: Run a list of neutral checks over one STEP and collect the results.

FILES (only these): `aturb/verify/runner.py`, `tests/test_verify_runner.py`

DO EXACTLY:

1. Create `aturb/verify/runner.py` with `run_checks(model: StepModel, checks) ->
list[CheckResult]`. A check is a callable that takes the model and returns
   one `CheckResult`. The runner calls each check in order and returns the
   results in the same order.
2. A check that raises is reported as a failure with the exception text, so one
   broken check never hides the others.
3. Create `tests/test_verify_runner.py`: two passing checks, one failing check,
   and one check that raises.

DO NOT: define a geometry schema, a DSL or a JSON description of geometry.

ACCEPTANCE:

- `uv run pytest tests/test_verify_runner.py -q` -> all pass

---

## T3.10 — Expected values for the demo project

GOAL: The demo project needs expected values that the agent may not change
silently.

FILES (only these): `projects/demo/expect/plt0001.toml`,
`aturb/verify/expectations.py`, `tests/test_verify_expectations.py`

DO EXACTLY:

1. Create `projects/demo/expect/plt0001.toml` holding expected measurements
   only: volume, bounding box, hole count, hole diameter and hole positions.
   Use the hand calculation already recorded in `tests/test_demo_plate.py`.
2. Create `aturb/verify/expectations.py` with `load_expectations(path: Path) ->
dict` and `checks_from_expectations(model: StepModel, expected: dict) ->
list[CheckResult]`, which turns each expected value into a `CheckResult`.
3. Create `tests/test_verify_expectations.py`: the committed fixture satisfies
   the demo expectations, and a wrong expected volume produces one failing
   result.

DO NOT: put geometry, a feature tree or a CAD operation in the expectation
file. It holds numbers only.

ACCEPTANCE:

- `uv run pytest tests/test_verify_expectations.py -q` -> all pass

---

## T3.11 — Demo project checks end to end

GOAL: Prove the neutral checks judge a real build, and that they work without
a CAD.

FILES (only these): `tests/test_demo_plate_checks.py`,
`tests/test_verify_fixture_checks.py`

DO EXACTLY:

1. Create `tests/test_demo_plate_checks.py`, marked `@pytest.mark.freecad`:
   build the demo plate through the real runner, then run the neutral checks
   over the exported STEP and assert every result passed.
2. Create `tests/test_verify_fixture_checks.py`: run the same checks over the
   committed fixture, with no CAD involved.

ACCEPTANCE:

- `uv run pytest tests/test_demo_plate_checks.py -q` -> 1 passed
- `uv run pytest tests/test_verify_fixture_checks.py -q` -> 1 passed

---

## T3.12 — CLI: aturb check

GOAL: Run the neutral checks of a part from the terminal.

FILES (only these): `aturb/cli.py`, `tests/test_cli.py`

DO EXACTLY:

1. Add an `aturb check <project_dir> <part_id> [--config PATH]` subcommand. It
   builds the part through the active pack, then runs the neutral checks over
   the exported STEP.
2. Print one line per check: `check <name> passed` or
   `check <name> failed: <message>`. Return 0 when every check passed, 1 when
   any check failed, and 2 for a configuration or pack error, like `build`.
3. Add tests to `tests/test_cli.py` using the stub pack and the committed
   fixture: all checks pass and return 0; a wrong expected value returns 1.

ACCEPTANCE:

- `uv run pytest tests/test_cli.py -q` -> all pass
- `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK

---

## T3.13 — Documentation

GOAL: The architecture document matches the code again.

FILES (only these): `docs/ARCHITECTURE.md`, `docs/api_notes/build123d.md`

DO EXACTLY:

1. Add a short section to `docs/ARCHITECTURE.md` describing the neutral
   verification layer: it reads an exported STEP with build123d, it lives in
   the core, and it never reads CAD-native diagnostics. Keep the file under
   110 lines.
2. Add any call that T3.02 to T3.12 verified and that is not yet in
   `docs/api_notes/build123d.md`, with the real output.

ACCEPTANCE:

- `docs/ARCHITECTURE.md` has under 110 lines
- `uv run python tools/agnostic_lint.py` -> agnostic_lint: OK

---

## T3.14 — Phase 3 cleanup and acceptance

GOAL: Remove what Phase 3 made obsolete and prove the phase is green.

FILES (only these): deletions inside `tools/spikes/` only

DO EXACTLY:

1. List every file in `tools/spikes/` and check whether it is still referenced
   in the docs, the API notes or a test. Delete the ones nothing uses, except
   `run_fc.py`, `fc_build.py`, `fc_hello.py` and the parts used by tests.
2. Run the full acceptance list: `uv run pytest -q`,
   `uv run pytest -m "not freecad" -q`, `uv run ruff check .`,
   `uv run python tools/size_limit.py`, `uv run python tools/agnostic_lint.py`.

ACCEPTANCE:

- every acceptance command passes
- the deleted files are listed in the report
