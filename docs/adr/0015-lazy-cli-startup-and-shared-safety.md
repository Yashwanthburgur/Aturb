# ADR-0015: Lazy CLI startup and shared safety primitives

## Status

Accepted.

## Context

The command line had become the slowest part of every invocation. Importing the
core pulled the geometry kernel and the numerical stack into memory even for
commands that never measure anything, so `aturb --help` paid for the whole
toolchain.

Three smaller problems sat next to it:

- The configuration path was accepted by some commands and not by others, so a
  caller could not point every command at one file.
- Persistence was written in more than one place, with more than one idea of
  what "written" means, and a reader could observe a half-written file.
- The viewer client repeated its own HTTP guards, its own body limit and its
  own credential handling in several modules, and the copies had drifted.

## Decision

1. **Lazy geometry-kernel imports.** The heavy modules — `OCP`, `build123d`,
   `numpy`, `scipy` and `sklearn` — are imported inside the functions that
   need them, never at module import time. `TYPE_CHECKING` keeps the type
   names available to a checker. The command line in
   [`aturb/cli.py`](../../aturb/cli.py) therefore reaches the kernel only when
   it actually measures a shape.

   A subprocess gate in
   [`tests/test_stabilization.py`](../../tests/test_stabilization.py) asserts
   that importing `aturb.cli` or `clients.viewer.cli` loads none of the five
   heavy modules. The gate runs in a fresh interpreter, so it measures the
   import and not the state of the test session.

   Measured over three runs on the development machine, the median import time
   of `aturb.cli` is `0.185 s`, of `clients.viewer.cli` `0.207 s`, of
   `uv run aturb --help` `0.334 s`, and of the viewer startup `0.366 s`.

2. **One configuration flag everywhere.** All seven subcommands — `build`,
   `check`, `assemble`, `edit-assembly`, `eval`, `generate` and `view` —
   accept `--config`. `aturb view --config` is threaded into all three viewer
   services, so the viewer reads the same file as the command line.

3. **Shared safety primitives.** Two modules now hold the primitives that used
   to be copied:
   - [`aturb/workspace/io.py`](../../aturb/workspace/io.py) writes a file
     atomically: a temporary file in the destination folder, `flush()`,
     `os.fsync()`, then `os.replace()`. This is atomicity for **one file**.
     It is not a transaction over several files, and it is not a database.
   - [`clients/viewer/http_utils.py`](../../clients/viewer/http_utils.py) holds
     the shared viewer guards: the body limit `MAX_BODY_BYTES = 65_536`, the
     content-length and JSON readers, the message sanitizer, and
     `SafeModelClient`, which keeps the credential out of every message it
     returns.

4. **Manifest-driven assembly presentation.** The browser inspector decides
   which panels to show from the manifest it already loads: an assembly
   manifest shows the engineering and assembly panels, a single-part manifest
   shows the part panels. The decision is made in one place, in
   [`clients/viewer/static/inspector.js`](../../clients/viewer/static/inspector.js),
   and no panel is hard-wired to a particular workspace.

## Consequences

- The command line starts without the geometry kernel, so a help call, a
  configuration error and a build no longer differ in import cost.
- One flag means one configuration file for the whole tool.
- The body limit and the credential handling are the same on every viewer
  endpoint, and a change in one module changes them everywhere.
- Atomicity is claimed only where it is true: for a single file. A reader can
  still see a workspace whose several files were written at different moments.
- The viewer shows the panels the manifest describes, so a new workspace kind
  needs a manifest change, not a change in the browser code.
