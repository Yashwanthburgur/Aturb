Architecture decision records, one per decision, 10 to 20 lines each.

- [ADR-0001: Code first](0001-code-first.md) — the model writes CAD code; there is no intermediate language and no tool per CAD operation.
- [ADR-0002: FreeCAD first](0002-freecad-first.md) — FreeCAD, run headless, is the first backend pack.
- [ADR-0003: Two Python environments](0003-two-pythons.md) — the core runs in the uv environment, part files run inside the CAD.
- [ADR-0004: Runner contract](0004-runner-contract.md) — one runner boundary; a runner never exposes CAD operations.
- [ADR-0005: Checks run on STEP](0005-checks-on-step.md) — correctness is judged only from the exported STEP.
- [ADR-0006: Task identity and answer schema](0006-task-identity-and-answer-schema.md) — the task ID and the part ID are separate, and the answer schema has five keys.
- [ADR-0007: Selection rule and helper boundary](0007-selection-rule-and-helper-boundary.md) — geometry is selected by its geometric properties; the helper selects, measures and asserts, and never creates a feature.
- [ADR-0008: Exclude expectations from the prompt](0008-exclude-expectations-from-prompt.md) — the expected values of the evaluator never reach the prompt.
- [ADR-0009: The bounded improvement loop](0009-bounded-improvement-loop.md) — the agent may try again a bounded number of times, and the repair feedback carries only what the candidate itself measures.
- [ADR-0010: Expectation-free arbitrary-prompt generation](0010-arbitrary-prompt-generation.md) — arbitrary requirements generate source and measured artifacts without evaluation fixtures or a correctness score, with isolated output on every attempt.
- [ADR-0011: Live STEP viewer and the client boundary](0011-live-step-viewer-and-client-boundary.md) — the browser viewer, the loopback-only server and the UI live in `clients/viewer/`; the core stays neutral, and the mesh comes from the verified neutral STEP tessellation.
- [ADR-0012: Iterative editing and the revision history](0012-iterative-editing-and-revisions.md) — every edit builds a new immutable `revisions/rNNNN/` workspace, `history.toml` names the active one, and a rollback selects a verified revision without deleting the later ones.
- [ADR-0013: Multi-part assemblies](0013-assemblies.md) — every part stays standalone and is built through the runner contract; an assembly is a portable manifest, composed and verified neutrally on exported STEP files, and an edit is promoted only when the whole assembly verifies.
