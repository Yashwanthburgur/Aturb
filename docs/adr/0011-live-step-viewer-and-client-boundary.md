# ADR-0011: Live STEP viewer and the client boundary

Date: 2026-11-25
Status: Accepted

## Context

Phase 8 leaves a portable workspace: a `result.toml` manifest, the editable
candidate source, the exported STEP and the native artifact of the active pack.
The engineering facts are in the manifest, but the geometry is only visible as a
file. A user who wants to look at a part needs a viewer, and the repository has
none.

Three constraints shape the decision.

The core is CAD-neutral, language-neutral and interface-neutral
([`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)). A browser, an HTTP server and a
user interface are an interface. They belong to a client, not to the core.

The repository is small on purpose. [`pyproject.toml`](../../pyproject.toml)
declares two runtime dependencies, `build123d` and `pyyaml`, and two development
dependencies, `pytest` and `ruff`. A viewer that needs a package manager, a
bundler and a runtime download from a content delivery network is a different
kind of project.

The command line is nearly full. [`aturb/cli.py`](../../aturb/cli.py) is 297 lines
and the limit is 300, so a new command has three lines to spend.

> **[Updated]** The line count was 295 when this record was written. The verified
> count today is **297 lines**, so the headroom below the 300-line limit is
> **three lines**, not five.

The facts below were measured in-session on 2026-11-25 and are the only facts
this record relies on.

## Verified facts

**The installed neutral STEP library.** `build123d` 0.13.0 is installed in the
project environment.

**The tessellation call.** `StepModel.shape` is a `Shape`; for a single-solid
file it is a `Solid`. The method is

```text
Shape.tessellate(self, tolerance: float, angular_tolerance: float = 0.1)
    -> tuple[list[Vector], list[tuple[int, int, int]]]
```

It returns a two-element tuple: `vertices`, a `list[Vector]`, and `triangles`,
a `list[tuple[int, int, int]]` of zero-based vertex indices. Each `Vector`
exposes `.X`, `.Y` and `.Z` and iterates as a three-element tuple. On the
committed fixture
[`packs/stub/fixtures/plate_2holes.step`](../../packs/stub/fixtures/plate_2holes.step),
`tessellate(0.1)` returned 1036 vertices and 1028 triangles, with indices from 0
to 1035, for a bounding box of 120 x 60 x 5 mm. `Shape.tessellate_with_uvs(...)`
and `Shape.mesh(...)` also exist; neither is needed.

**The agnosticism seam.** [`tools/agnostic_lint.py`](../../tools/agnostic_lint.py)
scans one directory only: `aturb/`, recursively, and only `*.py` files. Its
pattern is a case-insensitive, word-boundary regular expression over nine
backend brand and backend concept tokens, and it prints every matching line.
`build123d` matches none of them, and `docs/` is not scanned at all. The
modules of `aturb/` that name `build123d` are all in the neutral verification
layer: [`aturb/verify/step.py`](../../aturb/verify/step.py),
[`aturb/verify/holes.py`](../../aturb/verify/holes.py),
[`aturb/verify/cylinders.py`](../../aturb/verify/cylinders.py),
[`aturb/verify/interference.py`](../../aturb/verify/interference.py),
[`aturb/verify/engineering.py`](../../aturb/verify/engineering.py) and
[`aturb/verify/assembly.py`](../../aturb/verify/assembly.py).

> **[Updated]** The record said **four** modules. The verified count today is
> **six**: the engineering analysis and the assembly verification were added
> after this record was written.

**The size seam.** [`tools/size_limit.py`](../../tools/size_limit.py) scans
`aturb`, `packs`, `tools`, `tests` and `clients`, and only `*.py` files.
`clients/` is scanned, but `.html`, `.js` and `.css` files are not checked by
the tool. The 300-line rule for the browser assets is therefore a rule of this
phase, enforced by the card acceptance criteria, not by the tool.

**The command-line budget.** [`aturb/cli.py`](../../aturb/cli.py) is 297 lines: 297
newline characters and a trailing newline. The headroom below the 300-line
limit is exactly 3 lines.

> **[Updated]** The verified count today is **297 lines** and the headroom is
> **three lines**. The count of 295 and the headroom of five lines were
> correct when this record was written.

**The manifest.** `result.toml` holds `status`, `part_id`, `stop_reason`,
`attempts`, `input_tokens`, `output_tokens`, `cost_usd`, `prompt_version`,
`build_status`, `failure_kind`, `error`, `conventions`, `part_file`,
`step_file` and `native_file`, and, when the geometry was measured,
`is_valid`, `is_single_solid`, `volume`, `bbox_size`, `hole_count` and `holes`.
Every path in it is relative to the workspace root.

## Decision

**The viewer is a client, and the core does not know it exists.** The browser
assets, the HTTP server and the user interface live under `clients/viewer/`.
`aturb/` gains no HTML, no CSS, no JavaScript, no HTTP server and no browser
code. The client imports the core. The core domain packages — `aturb/agent/`,
`aturb/evals/`, `aturb/verify/`, `aturb/contract/` and `aturb/packs/` — never
import `clients/`; the only import of the client inside the core is the lazy
`from clients.viewer.cli import run_view_command` in the `view` branch of the
top-level entry point [`aturb/cli.py`](../../aturb/cli.py). The agnosticism lint
stays green because the core gains no new module and no new reference to a
backend.

**The tessellation seam is the verified one.** The client calls the core's
[`load_step()`](../../aturb/verify/step.py:90) and then the verified
`model.shape.tessellate(tolerance, angular_tolerance)` call, and converts the
returned `list[Vector]` and `list[tuple[int, int, int]]` into a JSON mesh of
positions and triangle indices. The conversion happens on demand, at the viewer
boundary, and only for the workspace that is open. The core is not changed and
no new dependency is added: `build123d` is already installed and already used
by the neutral verification layer.

**The mesh payload is JSON, not a binary format.** The payload carries the
vertex positions, the triangle indices and the two counts. JSON was chosen over
a binary mesh because it is inspectable without a tool, because the triangle
count is visible in the payload itself, and because the browser can parse it
without a decoder. A binary mesh was rejected for the same reason a content
delivery network is rejected: it adds a format the repository would have to
maintain.

**The viewport is zero-build, offline-safe WebGL.** The viewer is plain HTML,
CSS and JavaScript with the WebGL context of the browser. There is no Node.js,
no npm, no bundler and no external content delivery network dependency, so the
viewer renders with no network at all. The trade-off is explicit: hand-written
camera, matrix, shading and edge code is more work than importing a scene
graph, and the feature set is smaller, but the viewer works offline, works from
a plain copy of the folder, adds no dependency to
[`pyproject.toml`](../../pyproject.toml) and cannot break because a remote script
changed. The zero-dependency, offline-safe choice is locked.

**The phase has two stages.** Stage 1 is a read-only live 3D viewer: it loads
any `aturb generate` workspace, serves it over loopback-only HTTP, and shows
the geometry, the measured engineering facts and the artifact downloads. Stage 2
adds a prompt panel that posts a natural-language requirement to a loopback-only
endpoint, which calls the existing expectation-free
[`generate_part()`](../../aturb/agent/generate.py:68) and
[`write_generate_manifest()`](../../aturb/agent/generate_cli.py:32) into a fresh
timestamped workspace, and then updates the viewport and the panel. Stage 2
never creates a task, an answer or an expectation, never scores anything and
never shows a correctness claim.

**The server is loopback-only and workspace-contained.** The server binds to
`127.0.0.1` and never to `0.0.0.0`. The port is chosen by the operating system
by default and can be pinned with the `ATURB_VIEW_PORT` environment variable.
The only workspace files it can serve are the ones the manifest declares:
`part_file`, `step_file` and `native_file`. A request names a kind, never a
path. The server resolves the declared relative path against the workspace root
and refuses it unless the resolved path is inside the resolved workspace root,
so `..`, an absolute path and a symbolic link that escapes the root are all
refused. The browser assets bundled under `clients/viewer/static/` are served
from that one directory with the MIME type their extension implies, and a
request for an unknown asset or for one that leaves that directory is refused
with `404`.

**A mutating request must come from the local page.** `POST /api/generate`
checks the `Host` header against `127.0.0.1:<port>` and `localhost:<port>` for
the port the server actually bound to, and checks the `Origin` header, when one
is present, against `http://127.0.0.1:<port>` and `http://localhost:<port>` for
that same port. Any other host, scheme or port — including another port on the
same address — is refused with `403`. The provider credential stays on the
server: it is read from the environment variable that the configuration names,
it is never sent to the browser, and it never appears in a response body or in
an error message.

**A workspace without a usable STEP file is still a workspace.** A generation
that failed can leave a manifest whose `step_file`, `part_file` or
`native_file` is empty or absent. The viewer loads that manifest and shows its
status, its error, its advisory findings and the artifacts that do exist. The
page and the manifest answer `200`; the mesh and a missing artifact answer with
a structured JSON error — `404` when the artifact is absent, `422` when it is
present but cannot be turned into a mesh — and never with an unhandled server
error.

**The live run is recorded with pictures.** The baseline of the phase keeps the
screenshots of the rendered page — the viewport and the facts panel, for the
workspace that was opened and for the workspace the prompt produced — in the
git-ignored scratch folder, and names every file and what it shows. The
repository keeps the written record, not the image binaries.

**The command line spends exactly five lines.** T9.05 adds five lines to
[`aturb/cli.py`](../../aturb/cli.py) and lands it on exactly 300 lines:

1. `view = sub.add_parser("view")`
2. `view.add_argument("workspace")`
3. `if args.command == "view":`
4. `from clients.viewer.cli import run_view_command`
5. `return run_view_command(args)`

The import is lazy and sits inside the dispatch branch, so `build`, `check` and
`eval` never import the client package and their printed lines and exit codes
are untouched. The branch sits immediately after the argument parsing and
before the configuration block. No `--port` option is added: the port is an
environment setting, and adding a flag would cost a sixth line. The
consequence is recorded plainly: after T9.05 the command line has **zero**
remaining headroom, so any later command needs a new decision record or a
line-saving refactor.

> **[Updated]** Two statements above are no longer true. The `view` parser now
> **does** take a `--config` option, and the command line is **297 lines**, not
> 300, so the headroom is three lines. The `--config` flag of `view` is
> threaded into all three viewer services; the decision is recorded in
> [`docs/adr/0015-lazy-cli-startup-and-shared-safety.md`](0015-lazy-cli-startup-and-shared-safety.md).

**The client is importable, and its assets ship with it.** In this checkout the
editable install writes `_editable_impl_aturb.pth` with the repository root, and
`clients/` is a namespace package, so `clients.viewer` is importable. For a
built wheel, T9.05 adds `clients` to the wheel package list in
[`pyproject.toml`](../../pyproject.toml) and verifies that the static files under
`clients/viewer/static/` — the page, the stylesheet and the scripts — are
included as package data, because a wheel that carries the Python modules
without the browser assets would serve a viewer with no page. That is a
packaging change and adds no dependency.

**The frozen contracts stay frozen.** The runner contract and its eight failure
kinds, the five-field task result, the five-key answer specification, the
eleven-field agent run, the Phase 4 scoring rule, the `result.toml` schema,
`generate_part()`, `write_generate_manifest()`, `load_step()` and
`summarize_geometry()` are not changed. Phase 9 adds no dependency, no failure
kind, no geometry language, no operations layer, no multi-agent logic and no
background summarizer.

## Consequences

A user can look at a generated part in a browser, read the measured facts next
to it and download the source, the STEP and the native artifact, without the
core learning what a browser is.

The viewer is a client, so it can be replaced. A different front end, a
desktop window or a messaging bot would read the same manifest and the same
exported STEP, and the core would not change.

The tessellation seam is a verified call, not an assumed one. The version, the
signature, the return structure and the measured triangle count are recorded
above, so the next reader does not have to guess and the next card does not
have to re-derive them.

The zero-dependency choice costs hand-written browser code and a smaller
feature set, and it buys an offline viewer and an unchanged dependency list.
The five-line budget costs a command-line command and leaves the command line
nearly full, and it buys a core that stays free of interface code.

The loopback-only, workspace-contained server is a local single-user tool. It
has no authentication, no multi-user hosting and no cloud deployment, and it
is not a sandbox: it runs as the same operating-system user as the core.

A failed generation is still worth opening: the page shows what went wrong and
what was produced, instead of an empty screen or a server error.
