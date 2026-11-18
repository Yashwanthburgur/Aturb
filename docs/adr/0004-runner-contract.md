# ADR-0004: Runner contract

Date: 2026-11-18
Status: Accepted

## Context

The core must work with any CAD; PieCAD's tool layer exposed CAD operations and grew without bound.

## Decision

One runner boundary: in BuildRequest (project root, part ID, language tag, outputs, timeout), out BuildResult (status, failure kind, error text, log, artifacts, informational diagnostics, duration, contract version).
A runner never exposes CAD operations.
Runners are constructed with (settings, pack_dir).
CONTRACT_VERSION is checked when a pack is loaded.

## Consequences

Adding a CAD means writing one runner plus its pack files; the core does not change.
The contract changes only with a version bump and an ADR.
