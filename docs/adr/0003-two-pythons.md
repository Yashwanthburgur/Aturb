# ADR-0003: Two Python environments

Date: 2026-11-18
Status: Accepted

## Context

The core needs build123d for neutral measuring, while part files must run inside FreeCAD's own embedded Python.

## Decision

Two separate Python environments.
The core runs in the uv environment.
Part files and the harness run in FreeCAD's Python, launched as a subprocess.

## Consequences

The core never imports FreeCAD, and FreeCAD-side code never imports the core; they exchange only a request file in and a result file out.
This is the physical form of the runner contract.
