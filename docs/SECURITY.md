# Security

This document states what the repository actually enforces today, and what it does not.

## What is in place

- Part files pass a static check before running: an import allowlist, banned built-in
  calls, and no dunder attribute access ([`packs/freecad/precheck.py`](../packs/freecad/precheck.py)).
  The FreeCAD runner runs this check before it launches the CAD, so an unsafe or
  syntactically broken part file never reaches a child process.
- Builds run in a separate process with a minimal environment: only an allowlist of
  Windows variables is passed, plus the request path, so API keys, tokens and proxy
  settings are not passed to the part's process.
- A build is killed, with its child processes, after a timeout.
- Every part path and artifact path must stay inside the project folder. A path that
  escapes is refused, and an artifact outside the project is treated as a crash.

## What is NOT guaranteed

- The static check can be bypassed by sufficiently creative code. It is a first
  filter, not a sandbox.
- There is no operating-system-level network block or filesystem jail yet.
- The child process runs as the same operating-system user as the core, so it can
  still read files and open network connections that the user can.
- The static check covers the FreeCAD pack's part files only.

## Planned

- Run builds inside a container (or an equivalent OS sandbox) before any untrusted
  user can submit requests.
