Architecture decision records, one per decision, 10 to 20 lines each.

- [ADR-0001: Code first](0001-code-first.md) — the model writes CAD code; there is no intermediate language and no tool per CAD operation.
- [ADR-0002: FreeCAD first](0002-freecad-first.md) — FreeCAD, run headless, is the first backend pack.
- [ADR-0003: Two Python environments](0003-two-pythons.md) — the core runs in the uv environment, part files run inside the CAD.
- [ADR-0004: Runner contract](0004-runner-contract.md) — one runner boundary; a runner never exposes CAD operations.
- [ADR-0005: Checks run on STEP](0005-checks-on-step.md) — correctness is judged only from the exported STEP.
- [ADR-0006: Task identity and answer schema](0006-task-identity-and-answer-schema.md) — the task ID and the part ID are separate, and the answer schema has five keys.
- [ADR-0007: Selection rule and helper boundary](0007-selection-rule-and-helper-boundary.md) — geometry is selected by its geometric properties; the helper selects, measures and asserts, and never creates a feature.
