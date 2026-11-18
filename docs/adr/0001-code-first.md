# ADR-0001: Code first

Date: 2026-11-18
Status: Accepted

## Context

PieCAD spent about a month on about 20 hand-built tools, an intermediate representation, an MCP layer and a bridge.
Public evidence noted in our requirements (Adam's May 2026 post, Zoo's move to a code language, the AgenticCADedit paper, a GUI-agent benchmark on FreeCAD) points toward letting the model write CAD code.

## Decision

The model writes CAD code in the target CAD's own scripting language.
There is no intermediate language, JSON geometry schema, or tool per CAD operation.

## Consequences

Structure lives in project conventions, independent checks, and the eval set.
Burden-of-proof rule: any proposal to add a structured-operations layer must first beat the code path on the eval score, on the same tasks.
