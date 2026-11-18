# ADR-0002: FreeCAD first

Date: 2026-11-18
Status: Accepted

## Context

Users need a native, editable feature tree in their own CAD.
Each CAD exposes its own automation interface.

## Decision

FreeCAD, run headless, is the first backend pack.
Quality comes from a measured improvement loop, not a pass/fail exam.

## Consequences

Every future backend is also native, one pack per CAD.
Until a pack exists for a user's CAD, they receive STEP.
