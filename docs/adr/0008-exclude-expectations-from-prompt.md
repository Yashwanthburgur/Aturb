# ADR-0008: Exclude expectations from the prompt

Date: 2026-11-22
Status: Accepted

## Context

Phase 5 decision D7
([`docs/PHASE5_ROADMAP.md`](../PHASE5_ROADMAP.md:143)) put the expected values of
`project/expect/<part_id>.toml` into the composed agent prompt, between the
requirement and the output contract. The agent path reads that file and passes
its raw text to the prompt, so the model received the evaluator's expected
values before it wrote any code.

The committed task `plate_2holes` was not harmed by it: every value in its
expectation file — the volume, the bounding box, the hole count, the hole
diameter and the hole positions — is derivable from its engineering
requirement. The next tasks are not like that. The planned fillet task (T6.09)
carries a measured expected volume that cannot be derived from a requirement
written in plain language, so the same prompt would hand the model the number
the evaluation compares against.

The Phase 5 baseline was measured under D7, with the expectation file in the
prompt.

## Decision

**Phase 5 decision D7 is superseded.** The expected values of
`project/expect/<part_id>.toml` are no longer part of the prompt.

**Evaluator expectation files are never read into the agent prompt.** The agent
path does not read them, and no part of their content — values, comments or
paths — reaches the model.

**The prompt has five sections, in this order:**

1. the core instruction;
2. the pack prompt;
3. the project conventions;
4. the engineering requirement;
5. the output contract.

**The scratch workspace keeps `project/expect/`.** The evaluator reads the
expectation file from the scratch project and needs it there; only the prompt
loses it.

**The evaluator stays the judge.** The candidate is checked against the
expectation file by the neutral checks, independently of what the agent was
told.

This record states the decision. The code change that follows it is a separate
card.

## Consequences

The leakage of evaluator answers to the model is closed before T6.09, so the
task that needs a measured expected value cannot leak it.

The Phase 4 evaluation contracts, the scoring rule and the expectation files
are unchanged: the evaluator still reads the same files and still scores the
same way.

The Phase 5 baseline — the score of 0.60 and the prompt version
`872c1e7cb85a7709` — was measured under the old D7 information boundary. A
measurement taken after this decision uses a different information boundary and
must not be presented as directly comparable to it without that qualification.

A new baseline is recorded under the corrected architecture, with its own
prompt version.

Convention C6 of [`docs/CONVENTIONS.md`](../CONVENTIONS.md:133) describes the
expectation file as input the agent may not change. Under this decision the
agent no longer receives that file, so the wording of C6 is reconciled when the
amendment is implemented.
