# Project conventions

The conventions a part file of a project follows. They are written down here so
that two parts of the same project look the same and can be checked.

This document is project-level and CAD-neutral. It states six conventions, C1 to
C6, and nothing else: no CAD API, no backend brand, no geometry schema, no
configuration format.

**Source of truth.** The definitions below are the approved ones, taken from the
"Project conventions to establish" table of
[`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md). The architectural boundary is
[`docs/adr/0007-selection-rule-and-helper-boundary.md`](adr/0007-selection-rule-and-helper-boundary.md).
The scope of this document is the card T6.02 of
[`docs/PHASE6_TASKS.md`](PHASE6_TASKS.md). The rule IDs C1 to C6 are shared by
this document, by the checker and by the text the prompt carries, so the three
cannot drift apart.

## C1–C6 traceability table

Each convention appears exactly once in this table and exactly once in the
sections below. The definitions are quoted verbatim from the roadmap.

| ID  | Name                           | Exact approved definition                                                                                                         | Source                                        | Text-based checkability |
| --- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | ----------------------- |
| C1  | part identity                  | the part file is named `<part_id>_<name><extension>` and the part ID is the identity of the part                                  | [`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md) | Fully checkable         |
| C2  | parameter block                | the dimensions of the part are named constants at the top of the file, in a marked block, and every constant name ends with `_MM` | [`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md) | Fully checkable         |
| C3  | units                          | every length is in millimetres and the file says so                                                                               | [`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md) | Partially checkable     |
| C4  | placement                      | the part is centred on the origin in X and Y and spans Z = 0 to its thickness                                                     | [`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md) | Not reliably checkable  |
| C5  | no machine values              | no absolute path, no drive letter and no machine-specific value in the file                                                       | [`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md) | Partially checkable     |
| C6  | expectations are authoritative | the expectation file is input and is not changed by the agent without a declared reason                                           | [`docs/PHASE6_ROADMAP.md`](PHASE6_ROADMAP.md) | Not reliably checkable  |

## C1 — Part identity

**The rule.** the part file is named `<part_id>_<name><extension>` and the part
ID is the identity of the part

**Why it exists.** The project layout is fixed: a part is one file in the
project's parts folder, and the part ID is what names that part everywhere else,
including the expectation file `expect/<part_id>.toml`. The roadmap records that
the demo part already carries a part ID and that the project layout is fixed, but
that nothing stated either as a rule, so nothing could check them. Putting the
part ID in the file name makes the identity of a part visible where the part
lives, lets a reader find the part and its expectations, and lets the checker
compare the two. The task ID and the part ID remain two identifiers: the part ID
is never derived from the task ID
([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)).

**Text-based checkability.** Fully checkable

**Limitations.** The check compares the file name against the part ID and the
extension. It cannot confirm that the geometry inside the file is the part the
requirement describes, and it cannot confirm that the file builds.

## C2 — Parameter block

**The rule.** the dimensions of the part are named constants at the top of the
file, in a marked block, and every constant name ends with `_MM`

**Why it exists.** The dimensions of a part are the first thing a reader wants
and the first thing a reviewer checks. Named constants at the top of the file
make them readable without running a CAD, make two parts of the same project
comparable, and put a change to a dimension in one visible place. The `_MM`
suffix carries the unit in the name, so a value cannot be read with the wrong
unit. The roadmap records that the demo part already has such a block and that
nothing stated it as a rule, so nothing could check it.

**Text-based checkability.** Fully checkable

**Limitations.** The check covers the form of the block: that it is marked, that
it is at the top of the file, and that every constant name ends with `_MM`. It
cannot confirm that the constants are the true dimensions of the part, that every
dimension of the part is in the block, or that the constants are used
consistently in the body of the file.

## C3 — Units

**The rule.** every length is in millimetres and the file says so

**Why it exists.** A length without a unit is an ambiguous number. The rule has
two halves: the lengths are millimetres, and the file says so. The second half
is what makes the first half usable, because a reader and a checker can rely on
the statement without running anything. The roadmap records that the demo part
already uses named constants in millimetres and states its units.

**Text-based checkability.** Partially checkable

**Limitations.** Only the declaration is checkable: that the file states that
lengths are in millimetres. Whether every numeric value in the file is in fact a
length in millimetres is a property of the meaning of the code and of the built
geometry, and static text inspection cannot establish it.

## C4 — Placement

**The rule.** the part is centred on the origin in X and Y and spans Z = 0 to
its thickness

**Why it exists.** A part that sits somewhere arbitrary cannot be compared with
another part of the same project, and a measurement of it means little without a
known position. Fixing the placement gives every part of the project the same
frame of reference, so a measurement describes the part and not the place where
the part happens to sit. The roadmap assigns C4 to the neutral checks and to the
evaluation rather than to the text checker, because placement is a property of
the built geometry.

**Text-based checkability.** Not reliably checkable

**Limitations.** Placement is a runtime geometric property. Text inspection can
see the stated intent, such as a comment or a construction that appears centred,
but it cannot establish where the resulting solid actually lies. The neutral
checks and the evaluation judge C4.

## C5 — No machine values

**The rule.** no absolute path, no drive letter and no machine-specific value in
the file

**Why it exists.** A part file that carries an absolute path, a drive letter or
a machine-specific value builds only on the machine that wrote it. The
repository rule is the same: no absolute paths or machine-specific values in
committed files, use configuration
([`AGENTS.md`](../AGENTS.md)). Keeping the part file free of them makes a
project portable, makes the file reproducible on another machine, and keeps the
environment of whoever wrote it out of the part.

**Text-based checkability.** Partially checkable

**Limitations.** An absolute path and a drive letter are detectable in the text.
A machine-specific value in the general sense is not reliably detectable, because
the same text can be legitimate in one project and machine-specific in another,
and because the rule does not enumerate what counts as machine-specific.

## C6 — Expectations are authoritative

**The rule.** the expectation file is input and is not changed by the agent
without a declared reason

**Why it exists.** The expectation file holds the values the part must measure,
so it is the input that defines correctness. If the agent could change it, the
evaluation would compare the agent against its own output and would prove
nothing. The rule therefore makes the expectation file an input: the agent may
not change it without a declared reason. The demo expectation file states the
same thing in its own header.

**Text-based checkability.** Not reliably checkable

**Limitations.** C6 is about the state of the expectation file and the behaviour
of the agent, not about the text of a part file. A change to the expectation file
can be seen in a diff, but whether a declared reason exists, and whether a change
was legitimate, is judged by the evaluation. The roadmap assigns C6 to the
evaluation, not to the text checker.

## Boundaries

**Static text inspection is not a proof of geometry.** Static text inspection
cannot establish runtime geometric correctness or prove that the resulting CAD
geometry satisfies engineering intent. A convention that is checked from the
text of a file says that the file is written in the agreed form. It says nothing
about whether the built part is correct, whether its dimensions are the right
ones, or whether it answers the requirement. The neutral checks and the
evaluation remain the judges of correctness.

**Pack-specific conventions live in the pack.** Pack-specific conventions belong
in the corresponding pack prompt, not in this project-level document. The file
contract, the entry point, the feature order and the verified recipe of each
operation are specific to one CAD system and stay with that pack. The same holds
for the geometry-selection helper and for the rule that geometry is selected by
what it is and never by an assumed positional index: that boundary is recorded
in
[`docs/adr/0007-selection-rule-and-helper-boundary.md`](adr/0007-selection-rule-and-helper-boundary.md)
and belongs to the pack, not here. This document stays CAD-neutral and names no
CAD API, no backend and no implementation detail.

**The expectation file is authoritative.** The expectation file is authoritative
for correctness. The expected values in `expect/<part_id>.toml` define what the
part must measure; they are input to the evaluation, not output of it.

**The conventions are advisory.** Conventions are advisory and must never
independently trigger a refusal. A broken convention is a finding that is
reported; it never blocks a build, never becomes a failure of its own and never
changes the score of a task. The roadmap records the same risk: conventions that
are too strict would refuse valid solutions, so the checker is advisory and
never blocks a build.

**The agent must not modify evaluator expectations.** The agent must not modify
evaluator expectations. The expectation file is input, and the agent may not
change it without a declared reason.

## Which conventions the checker covers

The roadmap assigns the text checker (T6.03) to C1, C2, C3 and C5, the rules
that can be checked from the text of a file without a CAD. For C3 and C5 the
checker checks the part of the rule that text can establish: the statement of
the units, and the absence of an absolute path or a drive letter. C4 and C6 are
judged by the neutral checks and by the evaluation, not by the checker. The
classification above is consistent with that split.

## How the conventions appear in practice

The demo part
[`projects/demo/parts/plt0001_base_plate.py`](../projects/demo/parts/plt0001_base_plate.py)
follows all six:

- **C1** — the file is named `plt0001_base_plate.py`: part ID `plt0001`, name
  `base_plate`, extension `.py`.
- **C2** — the dimensions are named constants at the top of the file, in a block
  delimited by the marker comments `# --- PARAMS ---` and `# --- END PARAMS ---`,
  and every constant name ends with `_MM`: `LENGTH_MM`, `WIDTH_MM`,
  `THICKNESS_MM`, `HOLE_DIA_MM`, `HOLE_PITCH_MM`. The exact marker the checker
  accepts is defined by the checker (T6.03); this document fixes the rule, not
  the marker text.
- **C3** — the module docstring states `Units: millimetres`.
- **C4** — the module docstring states that the plate is centred on the origin
  in X and Y and spans Z = 0 to `THICKNESS_MM`.
- **C5** — the file holds no absolute path, no drive letter and no
  machine-specific value.
- **C6** — the expectation file
  [`projects/demo/expect/plt0001.toml`](../projects/demo/expect/plt0001.toml)
  holds numbers only and states that the agent may not change these values
  without a declared reason.
