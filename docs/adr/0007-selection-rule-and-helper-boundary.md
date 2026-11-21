# ADR-0007: Selection rule and helper boundary

Date: 2026-11-22
Status: Accepted

## Context

The agent writes CAD code and cannot look at the geometry it works on. The only
selection recorded so far is by index: the edge names of a fillet are
`"Edge" + str(index + 1)` (T1.25 in
[`docs/api_notes/freecad.md`](../api_notes/freecad.md)). An index is a position
in a list, not a property of the geometry, so it moves when the part changes.

Phase 6 wants a helper that lets the agent select existing geometry. A helper
that could also create features would be an operations layer, which
[`docs/adr/0001-code-first.md`](0001-code-first.md) refuses and
[`AGENTS.md`](../../AGENTS.md:23) forbids.

## Decision

**Geometry is selected by what it is.** A selection is made with geometric
properties and predicates — orientation, vertex coordinates, geometric type,
radius, position and other relevant properties of the geometry. Edges and
faces are never selected by an assumed positional index. The exact predicates
and the tolerances are not fixed here: they are measured in the implementation
and recorded in [`docs/api_notes/freecad.md`](../api_notes/freecad.md).

**The helper is a geometry-selection utility.** It may:

- select geometry by its geometric properties;
- measure geometry;
- inspect faces and edges;
- assert the properties of a selection;
- return the actual identifiers and names of the selected geometry, so the
  agent can use them in the code it writes.

It may not:

- create a feature of any kind — no pad, no pocket, no fillet, no hole;
- modify the feature tree;
- execute the engineering operation on behalf of the agent.

**The agent keeps the engineering responsibility.** The agent understands the
engineering requirement, chooses the operation, creates the CAD feature, sets
its parameters and handles the resulting geometry. The helper answers "which
edges are these?"; the agent still writes "fillet these edges".

**The helper lives in the pack.** It belongs in
[`packs/freecad/`](../../packs/freecad/), next to the harness, and it runs inside
the CAD's own Python ([`docs/adr/0003-two-pythons.md`](0003-two-pythons.md)).
No FreeCAD-specific functionality is introduced into `aturb/`.

**The security boundary does not move.** The static precheck of the FreeCAD
pack ([`packs/freecad/precheck.py`](../../packs/freecad/precheck.py)) is not
weakened and its import allowlist is not widened as part of this decision. The
mechanism that delivers the helper to the part file is experimentally verified
first, in T6.05, and recorded in
[`docs/api_notes/freecad.md`](../api_notes/freecad.md). If no safe mechanism
exists, the helper does not ship and the phase reports it.

## Consequences

The agent can name the geometry it works on without guessing an index, and the
helper cannot grow into an operations layer: the boundary is testable, because
a helper that creates a feature can be refused by a test.

The helper is CAD-specific and lives in the pack, so a second CAD needs its
own helper and the core stays unchanged. The selection predicates are measured
facts, not assumptions, and they are recorded where the other verified calls
are recorded.
