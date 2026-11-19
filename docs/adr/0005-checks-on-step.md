# ADR-0005: Checks run on STEP

Date: 2026-11-18
Status: Accepted

## Context

Each CAD reports errors differently; the agent must never certify its own work (v2 P3).

## Decision

Correctness is judged only from facts measured on the exported STEP with one neutral library.
BuildResult.native_diagnostics are informational and shown to the agent as hints, never used to pass or fail a check.

## Consequences

The same checks apply to every backend.
A backend that cannot export STEP cannot pass checks.
