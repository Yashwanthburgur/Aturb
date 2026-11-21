# Phase 6 task roadmap — conventions and selection helper

Proposed task cards for Phase 6, derived from the Phase 5 roadmap
([`docs/PHASE5_ROADMAP.md`](PHASE5_ROADMAP.md)), the architecture
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)), the decision records
([`docs/adr/`](adr/README.md)) and the Phase 5 baseline
([`docs/PHASE5_BASELINE.md`](PHASE5_BASELINE.md)).

Scope: two things that make the output of the agent more consistent — a written
set of project conventions, and a helper that selects existing geometry by what
it is. The agent keeps writing CAD code. The helper may select, measure and
assert; it never creates a feature.

## Where this roadmap lives

The implementation guide Part 3 (Phases 5–6) is not in this repository. The
project map in [`docs/IMPLEMENTATION_GUIDE_PART1.md`](IMPLEMENTATION_GUIDE_PART1.md:72)
lists Phase 6 as "Conventions and selection helper", task IDs `T6.xx`, about 48
tasks, in Part 3. As with Phases 4 and 5, the roadmap is split in two: this
file holds the scope, the decisions and the strategy, and
[`docs/PHASE6_TASKS.md`](PHASE6_TASKS.md) holds the cards T6.01 to T6.12. This
plan proposes 12 cards; the guide's estimate of about 48 is larger, and the
difference is left open in the questions at the end of this file.

## Objective

Make the CAD output of the agent follow consistent project conventions, and
give the agent a reliable way to select geometry that already exists.

The agent still generates CAD code; the helper only selects, measures and
asserts, and it returns the identifiers the agent needs.

The phase has two deliverables that can be measured separately:

1. A written set of project conventions, a checker for the part of them that
   can be checked without a CAD, and the conventions in the prompt of the agent.
2. A selection helper in the FreeCAD pack that selects edges and faces by
   their geometric properties, delivered by a mechanism that is verified before
   it is used.

## Current architectural context after Phase 5

- The core is CAD-neutral and language-neutral. Everything specific to one CAD
  lives in `packs/<name>/` ([`docs/ARCHITECTURE.md`](ARCHITECTURE.md:50)).
- The agent path is one task, one model call, one candidate file, one build and
  one score: [`run_agent()`](../aturb/agent/run.py:43) composes the prompt,
  calls the model once and writes the candidate into a scratch copy of the
  task; [`run_task()`](../aturb/evals/runner.py:40) builds that candidate and
  scores it with the neutral checks.
- The prompt is composed in a fixed order — core instruction, pack prompt,
  requirement, expectations, output contract — and named by the hash of its
  text ([`compose_prompt()`](../aturb/agent/prompt.py:33)). The pack owns the
  instructions of the agent
  ([`packs/freecad/prompt/agent.md`](../packs/freecad/prompt/agent.md)), and
  the core reads them as opaque text.
- The runner contract carries no CAD operation
  ([`docs/adr/0004-runner-contract.md`](adr/0004-runner-contract.md)), and the
  checks run on the exported STEP
  ([`docs/adr/0005-checks-on-step.md`](adr/0005-checks-on-step.md)).
- The part file runs inside the CAD's own Python and never imports the core
  ([`docs/adr/0003-two-pythons.md`](adr/0003-two-pythons.md)).
- The FreeCAD pack checks every part file statically before the CAD is
  launched: an import allowlist, banned built-in calls and no dunder access
  ([`packs/freecad/precheck.py`](../packs/freecad/precheck.py:7)).

## Problems revealed by the Phase 5 baseline

The baseline is one measured run of the stock agent on the one committed task
([`docs/PHASE5_BASELINE.md`](PHASE5_BASELINE.md)). It scored 0.6: the bounding
box passed, the volume and the hole count failed.

1. **The agent wrote code that looked right and did nothing.** The candidate
   padded a rectangle and cut the holes with a `ThroughAll` pocket, but the
   pocket cut no material: the exported solid was the plain 120 × 60 × 5 plate
   of 36000 mm³ with no hole in it. The pack prompt already records the
   verified recipe — `PartDesign::Pocket` with `ThroughAll` cuts, the
   `PartDesign::Hole` feature does not cut in headless FreeCAD 1.0.1 (T1.26) —
   and the agent still got it wrong. The agent needs the conventions of the
   project written down, not only a list of calls.
2. **The agent could not look at the geometry it was working on.** It writes
   code blind: it has no way to ask what an edge or a face is. The only
   selection recorded so far is by index — the edge names of a fillet are
   `"Edge" + str(index + 1)` (T1.25) — which is exactly the fragile way to
   select geometry.
3. **The project has conventions, but they are not written down.** The demo
   part file has a parameter block, named constants in millimetres, a part ID
   and a placement rule
   ([`projects/demo/parts/plt0001_base_plate.py`](../projects/demo/parts/plt0001_base_plate.py)),
   and the project layout is fixed
   ([`evals/tasks/plate_2holes/`](../evals/tasks/plate_2holes)). Nothing states
   them as rules, so nothing can check them.
4. **One task cannot show selection.** The committed task needs no selection:
   the holes are placed by coordinates in a sketch. A task that needs a fillet
   on existing edges is needed before selection can be measured.

## Project conventions to establish

The conventions are the rules a part file follows so that two parts of the same
project look the same and can be checked. They are written down in
`docs/CONVENTIONS.md` (T6.02) and split in two layers.

Project conventions, CAD-neutral:

| rule                              | what it says                                                                                                                      |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| C1 part identity                  | the part file is named `<part_id>_<name><extension>` and the part ID is the identity of the part                                  |
| C2 parameter block                | the dimensions of the part are named constants at the top of the file, in a marked block, and every constant name ends with `_MM` |
| C3 units                          | every length is in millimetres and the file says so                                                                               |
| C4 placement                      | the part is centred on the origin in X and Y and spans Z = 0 to its thickness                                                     |
| C5 no machine values              | no absolute path, no drive letter and no machine-specific value in the file                                                       |
| C6 expectations are authoritative | the expectation file is input and is not changed by the agent without a declared reason                                           |

Pack conventions, one per pack, in the pack prompt: the file contract, the
entry point, the feature order and the verified recipe of each operation. They
stay in the pack, because they are specific to one CAD
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md:52)).

The checker (T6.03) checks C1, C2, C3 and C5, the rules that can be checked
from the text of a file without a CAD. C4 and C6 are judged by the neutral
checks and by the evaluation, not by the checker. The pack conventions are
checked by the tests of the pack.

The rule IDs C1 to C6 are shared by the document, the checker and the text the
prompt carries, so the three cannot drift apart. The prompt gains a sixth
section, the conventions, and the prompt version changes with it: the prompt
version of the Phase 5 baseline no longer matches the prompt of Phase 6, and
the Phase 6 baseline records the new one.

## Selection-helper architecture

The helper is a module of the FreeCAD pack, next to the harness:
`packs/freecad/helper/select.py`. It runs inside the CAD's Python, like the
harness does, and it never imports the core.

It may:

- select edges and faces by their geometric properties and predicates;
- measure geometry;
- inspect faces and edges;
- assert the properties of a selection;
- return the actual identifiers and names of the selected geometry, so the
  agent can use them in the code it writes.

It may not:

- create a feature of any kind — no pad, no pocket, no fillet, no hole;
- modify the feature tree;
- execute the engineering operation on behalf of the agent.

The agent stays responsible for the engineering: it reads the requirement,
chooses the operation, creates the feature, sets its parameters and handles the
resulting geometry. The helper answers "which edges are these?"; the agent
still writes "fillet these edges".

The rule that decides the selection is recorded in
[`docs/adr/0007-selection-rule-and-helper-boundary.md`](adr/0007-selection-rule-and-helper-boundary.md):
geometry is selected by what it is — orientation, vertex coordinates,
geometric type, radius, position and other relevant properties — and never by
an assumed positional index.

## Helper delivery mechanism

The helper has to reach the part file, and the part file runs inside the CAD
process under a static check. The mechanism is therefore not a free choice:

- The precheck allows only the imports `FreeCAD`, `Part`, `PartDesign`,
  `Sketcher` and `math`, and bans `open`, `exec`, `eval`, `compile`,
  `__import__` and dunder access
  ([`packs/freecad/precheck.py`](../packs/freecad/precheck.py:7)). A part file
  that imports a helper module by name is refused today.
- The child process gets a minimal environment and one request file
  ([`docs/SECURITY.md`](SECURITY.md:11)), so the helper cannot be fetched from
  outside, and the core and the CAD run in two Python environments
  ([`docs/adr/0003-two-pythons.md`](adr/0003-two-pythons.md)), so the helper
  cannot be a core module.

Three mechanisms are candidates, and T6.05 tests them in the real CAD before
any of them is used:

1. the harness loads the helper and puts it where the part file can reach it
   without an import;
2. the helper is copied into the project and the part file loads it by path;
3. the helper is exposed through the document the harness gives to the part
   file.

Which one works is a fact to be measured, not a fact to be assumed. T6.05
records the result in [`docs/api_notes/freecad.md`](api_notes/freecad.md). If
no mechanism is safe, the phase stops and reports it: the precheck is not
weakened and its import allowlist is not widened to make a mechanism work.

## Evaluation strategy

The phase is measured the way Phase 5 was measured: a recorded run, not a
function that can be replayed.

- The task set grows by one task that needs selection: a plate with a fillet
  on its vertical corner edges (T6.09). The expected values come from the
  measurement recorded in T1.25 — a volume of 35175.973506 mm³ for the
  filleted plate with its two holes, and the same bounding box as the plate
  without the fillet — and the task card verifies them by building the
  reference part.
- The task uses the existing task format, the five-key answer schema and the
  existing neutral checks. No schema changes.
- The agent is run over the task set with the conventions in the prompt and the
  helper available (T6.10), and the result is written down with the model, the
  prompt version, the tokens and the cost (T6.11), in the shape of
  [`docs/PHASE5_BASELINE.md`](PHASE5_BASELINE.md).
- The comparison is with the Phase 5 baseline: the same task set, the same
  scoring rule and the same neutral checks. A model call is not deterministic,
  so the comparison is between two recorded measurements, not two functions.

## Dependencies and task sequence

T6.01 → T6.02 → T6.03 → T6.04 → T6.05 → T6.06 → T6.07 → T6.08 → T6.09 → T6.10
→ T6.11 → T6.12

T6.05 (the delivery spike) may run in parallel with T6.02, T6.03 and T6.04,
because it is an experiment and changes no file of the product. T6.06 waits for
T6.05, because the helper can only be written for a mechanism that is known to
work. T6.09 waits for T6.02, because the second task follows the conventions.
Every other card waits for the card before it. The cards are in
[`docs/PHASE6_TASKS.md`](PHASE6_TASKS.md).

## Acceptance criteria

The phase is accepted when:

- the conventions are written down, the checker checks the rules that can be
  checked without a CAD, and the conventions are in the prompt of the agent;
- the helper selects geometry by its geometric properties, never by an assumed
  index, and creates no feature;
- the helper is delivered by a mechanism that was measured in T6.05, with the
  precheck and its import allowlist unchanged;
- the second task is in the task set and is scored by the existing pipeline
  with the existing schemas;
- the Phase 6 baseline is written down next to the Phase 5 baseline;
- `uv run pytest -m "not freecad" -q`, `uv run pytest -q`,
  `uv run ruff check .`, `uv run python tools/size_limit.py` and
  `uv run python tools/agnostic_lint.py` all pass, and the runner contract,
  the answer schema, the result record and the agent-run record are unchanged.

## Scope boundaries and exclusions (locked for Phase 6)

Phase 6 does not introduce:

- a runner contract change or a contract version bump: [`BuildRequest`](../aturb/contract/types.py:26),
  [`BuildResult`](../aturb/contract/types.py:58),
  [`PackInfo`](../aturb/contract/types.py:113) and
  [`Runner`](../aturb/contract/runner.py:10) stay as they are, the contract
  version is not bumped and no failure kind is added;
- a new failure kind;
- an answer-schema change, an evaluation-result schema change or an AgentRun
  record change;
- a geometry DSL or an intermediate representation
  ([`docs/adr/0001-code-first.md`](adr/0001-code-first.md));
- a feature-creation helper: the helper selects, measures and asserts
  ([`AGENTS.md`](../AGENTS.md:27));
- a ReAct loop or a retry loop;
- multi-agent orchestration;
- GUI functionality;
- a new external dependency;
- a CAD-specific concept inside `aturb/`.

Phase 7 and later are outside this assignment.

## Architectural risks

| risk                                             | what it would break                                                               | what keeps it small                                                                                              |
| ------------------------------------------------ | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| R1 the precheck refuses every delivery mechanism | the helper cannot reach the part file                                             | T6.05 measures the mechanisms first; the precheck is not weakened, and the phase stops and reports if none works |
| R2 the helper grows into an operations layer     | the code-first decision ([`docs/adr/0001-code-first.md`](adr/0001-code-first.md)) | the boundary is in ADR-0007 and a test refuses a helper that creates a feature                                   |
| R3 a wrong tolerance selects the wrong edge      | the agent fillets the wrong geometry                                              | the helper asserts the number of selected items and their properties, and the agent sees the assertion           |
| R4 the helper needs the core                     | the two-Python rule breaks                                                        | the helper is self-contained in the pack and imports nothing from `aturb/`                                       |
| R5 the conventions are too strict                | valid solutions are refused                                                       | the checker is advisory and never blocks a build                                                                 |
| R6 one model call is noisy                       | the comparison with the baseline is not a proof                                   | the baseline records the model, the prompt version and the date, and is compared like with like                  |
| R7 the helper becomes a second judge             | the checks on STEP stop being the only judge                                      | the helper only reports; the neutral checks still decide the score                                               |

## Relationship with Phase 7

Phase 7 is the improvement loop: the agent sees what failed and tries again.
Phase 6 gives that loop better inputs — a part file that follows the
conventions and a reliable way to select geometry — but does not implement it.

- Phase 6 keeps one model call per task. The `attempts` field of the agent-run
  record stays at `1` and the record does not grow.
- The conventions and the helper are inputs of the prompt, so Phase 7 reuses
  them unchanged.
- The Phase 6 baseline is the measurement Phase 7 starts from.

## Open questions

- The guide estimates about 48 tasks for Phase 6
  ([`docs/IMPLEMENTATION_GUIDE_PART1.md`](IMPLEMENTATION_GUIDE_PART1.md:72));
  this plan proposes 12 cards. The difference is left open: the cards are the
  plan, and the estimate of the guide was not revised.
- Which delivery mechanism works is measured in T6.05, not decided here.
- The tolerances of the selection predicates are not decided here: they belong
  to the implementation and the verification of T6.06, and they are recorded in
  [`docs/api_notes/freecad.md`](api_notes/freecad.md) when they are measured.
