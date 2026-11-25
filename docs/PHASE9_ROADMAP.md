# Phase 9 roadmap — live 3D STEP viewer and interactive UI

Phase 9 adds a browser viewer for a generated workspace. It follows the
architecture ([`docs/ARCHITECTURE.md`](ARCHITECTURE.md)), the code-first and
runner decisions, the neutral-measurement decision and the expectation-free
generation decision of ADR-0001 through ADR-0010. Its new architectural decision
is
[`docs/adr/0011-live-step-viewer-and-client-boundary.md`](adr/0011-live-step-viewer-and-client-boundary.md).

Scope: one thing — let a person see the geometry of a generated part, read its
measured facts, download its artifacts, and later ask for a new part from the
same page. The work is split into the cards in
[`docs/PHASE9_TASKS.md`](PHASE9_TASKS.md).

## Current state after Phase 8

- `aturb generate` writes a standalone workspace with the candidate source, the
  build products and a portable `result.toml` manifest.
- The manifest holds the run status, the usage, the build outcome, the advisory
  findings and the measured geometry, with relative paths only.
- The neutral verification layer reads an exported STEP with the installed
  `build123d` 0.13.0 and measures it.
- The measured facts are visible only as text. The geometry is visible only as
  a file that has to be opened in another program.
- No server, no browser interface and no interactive prompt path exist.

## Objective

Serve any `aturb generate` workspace over loopback-only HTTP and show it in a
browser: an interactive 3D viewport, the measured engineering facts and the
artifact downloads. Then, in the same page, let the user type a requirement and
watch a new part appear. Success means that the browser shows the geometry that
the exported STEP actually holds and the facts that the manifest actually
records. It does not mean that the part satisfies an engineering target.

## Decisions

**D1 — The viewer is a client.** The browser assets, the HTTP server and the
user interface live under `clients/viewer/`. `aturb/` gains no HTML, no CSS, no
JavaScript, no HTTP server and no browser code. The client imports the core.
The core domain packages — `aturb/agent/`, `aturb/evals/`, `aturb/verify/`,
`aturb/contract/` and `aturb/packs/` — never import `clients/`; the only
import of the client inside the core is the lazy import in the `view` branch of
[`aturb/cli.py`](../aturb/cli.py).

**D2 — The core stays CAD-neutral, language-neutral and interface-neutral.**
[`tools/agnostic_lint.py`](../tools/agnostic_lint.py) scans only `aturb/**/*.py`
for the forbidden backend tokens, and `build123d` is not one of them. The core
gains no new module and no new backend reference, so the lint stays green by
construction.

**D3 — The tessellation seam is the verified one.** The client calls the core's
[`load_step()`](../aturb/verify/step.py:90) and then the verified
`model.shape.tessellate(tolerance, angular_tolerance)` call, which returns
`tuple[list[Vector], list[tuple[int, int, int]]]`. The conversion happens on
demand, at the viewer boundary, for the open workspace only. No new dependency
is added.

**D4 — The mesh payload is JSON.** The payload carries the vertex positions, the
triangle indices and the two counts. It is inspectable without a tool and needs
no decoder in the browser.

**D5 — The viewport is zero-build, offline-safe WebGL.** Plain HTML, CSS and
JavaScript with the WebGL context of the browser. No Node.js, no npm, no
bundler, no external content delivery network dependency. The trade-off is
recorded: hand-written camera, matrix, shading and edge code is more work than
importing a scene graph and the feature set is smaller, but the viewer renders
with no network, works from a plain copy of the folder and adds no dependency.

**D6 — The server is loopback-only.** It binds to `127.0.0.1` and never to
`0.0.0.0`. The port is chosen by the operating system by default and can be
pinned with the `ATURB_VIEW_PORT` environment variable.

**D7 — Only declared files are served.** The request names a kind, never a path.
The kinds are `part_file`, `step_file` and `native_file`, taken from the
manifest. The server resolves the declared relative path against the workspace
root and refuses it unless the resolved path is inside the resolved workspace
root, so `..`, an absolute path and a symbolic link that escapes the root are
refused. The browser assets bundled under `clients/viewer/static/` are served
from that one directory with the MIME type their extension implies, and an
unknown asset or one that leaves that directory is refused with `404`.

**D8 — A mutating request must come from the local page.** `POST /api/generate`
checks the `Host` header against `127.0.0.1:<port>` and `localhost:<port>` for
the port the server actually bound to, and checks the `Origin` header, when one
is present, against `http://127.0.0.1:<port>` and `http://localhost:<port>` for
that same port. Any other host, scheme or port, including another port on the
same address, is refused with `403`. The provider credential is read from the
environment variable the configuration names and is never sent to the browser,
never returned and never printed.

**D9 — Stage 1 is read-only.** It loads a workspace, serves it and shows it.
It never writes into the workspace and never calls the model.

**D10 — Stage 2 reuses the existing generation path.** The endpoint calls the
existing expectation-free [`generate_part()`](../aturb/agent/generate.py:68) and
[`write_generate_manifest()`](../aturb/agent/generate_cli.py:32) into a fresh
timestamped workspace, then switches the open workspace to it. It never creates
a task, an answer or an expectation, never scores anything and never shows a
correctness claim.

**D11 — The command line spends exactly five lines.** [`aturb/cli.py`](../aturb/cli.py)
is 295 lines and the limit is 300. T9.05 adds five lines and lands it on
exactly 300: the `view` parser, its workspace argument, the dispatch branch, a
lazy import of the client entry point and the delegation. The import is inside
the branch, so `build`, `check` and `eval` never import the client package and
their printed lines and exit codes are untouched. No `--port` flag is added,
because a sixth line does not exist. After T9.05 the command line has zero
remaining headroom.

**D12 — The phase adds no dependency and changes no contract.** The runner
contract and its eight failure kinds, the five-field task result, the five-key
answer specification, the eleven-field agent run, the Phase 4 scoring rule and
the `result.toml` schema are unchanged.

**D13 — A workspace without a usable STEP file is still a workspace.** A failed
generation can leave a manifest whose `step_file`, `part_file` or `native_file`
is empty or absent. The loader returns no artifact for a missing one and still
loads the other manifest fields. The page and the manifest answer `200`; the
mesh and a missing artifact answer with a structured JSON error, `404` when the
artifact is absent and `422` when it is present but cannot be meshed, and never
with an unhandled server error. The viewport shows an empty state and the
inspector still shows the status, the error, the advisory findings and the
downloads that do exist.

**D14 — The live run is recorded with pictures.** The baseline keeps the
screenshots of the rendered page, for the workspace that was opened and for the
workspace the prompt produced, in the git-ignored scratch folder, and names
every file and what it shows. The repository keeps the written record, not the
image binaries.

**D15 — The 300-line policy is flagged, not changed.** The file-size tool
checks Python source files only. This phase changes neither the tool nor the
rule, and it flags the points that need a project-level review.

## Stage 1 sequence — read-only live 3D viewer

1. Resolve the workspace argument to an absolute path and read its
   `result.toml`.
2. Resolve the declared artifact paths against the workspace root and refuse
   anything that leaves it.
3. Read the exported STEP with the core's neutral reader and tessellate it with
   the verified call.
4. Serve the page, the manifest, the mesh and the three declared files over
   loopback-only HTTP.
5. Draw the mesh, the axes and the bounding box, and fill the panel with the
   measured facts of the manifest.

## Stage 2 sequence — interactive prompt-to-3D

1. The page posts a natural-language requirement to `POST /api/generate`.
2. The server checks the local origin and the local host.
3. The server calls the existing generation service into a fresh timestamped
   workspace and writes its manifest.
4. The server switches the open workspace to the new one and answers with the
   new workspace identity, the status and the stop reason.
5. The page re-reads the manifest and the mesh and updates the viewport and the
   panel.

The generation call is synchronous. The page shows a busy state while it runs.
There is no background job, no queue and no streaming.

## HTTP surface

| Method | Path                | Answer                                                    |
| ------ | ------------------- | --------------------------------------------------------- |
| `GET`  | `/`                 | the viewer page                                           |
| `GET`  | `/api/manifest`     | the measured facts of the open workspace, as JSON         |
| `GET`  | `/api/mesh`         | the tessellated mesh of the open workspace, as JSON       |
| `GET`  | `/api/files/<kind>` | the declared artifact, where `<kind>` is one of the three |
| `GET`  | `/<asset>`          | a browser asset from `clients/viewer/static/`             |
| `POST` | `/api/generate`     | the new workspace identity, status and stop reason        |

`<kind>` is one of `part_file`, `step_file` and `native_file`. Any other value
is refused. The request never carries a path.

| Situation                                         | Answer                               |
| ------------------------------------------------- | ------------------------------------ |
| the workspace has no usable STEP file             | `/` and `/api/manifest` answer `200` |
| the mesh or the STEP artifact is absent           | `404`, with a structured JSON body   |
| the STEP artifact is present but cannot be meshed | `422`, with a structured JSON body   |
| an unknown or escaping browser asset              | `404`                                |
| a mutating request with a foreign host or port    | `403`                                |

## Mesh payload

| Field            | Meaning                                             |
| ---------------- | --------------------------------------------------- |
| `vertices`       | the vertex positions, three numbers each            |
| `triangles`      | the triangle indices, three zero-based indices each |
| `vertex_count`   | the number of vertices                              |
| `triangle_count` | the number of triangles                             |

The starting default of the tessellation tolerance is `0.1` millimetres, with
the verified default angular tolerance of `0.1` radians. On the committed
fixture [`packs/stub/fixtures/plate_2holes.step`](../packs/stub/fixtures/plate_2holes.step)
that call returned 1036 vertices and 1028 triangles. The browser derives the
shading normals and the bounding box from the payload.

## Security boundary

- The server binds to `127.0.0.1` and never to `0.0.0.0`.
- Only the three declared artifacts and the browser assets are served.
- Every workspace path is resolved and checked against the workspace root, and
  every asset path against `clients/viewer/static/`.
- A mutating request must carry a `Host` and an `Origin` that name the bound
  port exactly.
- The provider credential stays in the server environment.
- There is no authentication, no multi-user hosting and no cloud deployment.
- The server is not a sandbox: it runs as the same operating-system user as the
  core.

## Evaluation strategy

- Unit tests prove the manifest loader, the path containment rules and the
  mesh conversion, including the refusal of `..`, of an absolute path and of a
  symbolic link that escapes the root, and the loading of a manifest whose
  artifacts are empty or absent.
- Server tests prove the loopback binding, the read-only routes, the serving of
  the browser assets with their MIME types, the refusal of an unknown kind, of
  an escaping asset path and of a foreign origin, and the structured `404` and
  `422` answers of a workspace without a usable STEP file.
- Browser-side tests are not automated in this phase; the viewport is proved by
  the live run of T9.07 and by the recorded measurements of that run.
- A real-backend test proves that a built part exports a STEP that tessellates
  into a non-empty mesh.
- The full existing suite proves that the evaluation and runner contracts did
  not move.
- No implementation test makes a live-model or network call.

## Dependencies and task sequence

T9.01 → T9.02 → T9.03 → T9.04 → T9.05 → T9.06 → T9.07

T9.01 fixes the architecture and the cards. T9.02 builds the loader and the
tessellation, T9.03 the server, T9.04 the viewport, T9.05 the command, T9.06
the interactive endpoint and the prompt panel. T9.07 is the live verification
and is deferred until the other cards pass their gates.

## Acceptance criteria

- Any `aturb generate` workspace opens in a browser and shows its geometry.
- The viewport orbits, pans and zooms, and shows a shaded view, an edge view,
  the axes and the bounding box.
- The panel shows the measured facts of the manifest and the three artifact
  downloads work.
- The server binds to `127.0.0.1` only and serves only the declared files and
  the browser assets.
- A path that leaves the workspace or the asset directory is refused.
- A workspace without a usable STEP file still opens, and the mesh and the
  missing artifact answer with a structured error and never with an unhandled
  server error.
- A mutating request with a host, a scheme or a port other than the bound one
  is refused with `403`.
- A prompt typed in the page produces a new workspace whose geometry and facts
  appear without a page reload.
- No credential reaches the browser.
- The core gains no interface code and the agnosticism lint stays green.
- Every implementation file of the phase is at most 300 lines, including the
  browser assets.
- The offline and full suites, the lint, the file-size and the agnosticism
  gates pass.

## Scope boundaries and exclusions

Phase 9 does not introduce a runner contract change, a ninth failure kind, an
answer or result schema change, a geometry DSL, an intermediate representation,
an operations layer, a framework, autonomous tool calling, multi-agent logic, a
background summarizer, a design graph, a feature-tree editor, an expectation or
scoring interface, authentication, multi-user hosting, a cloud deployment or a
new external dependency. It does not modify the committed task set or the
frozen evaluation pipeline.

## The 300-line policy, flagged for review

[`tools/size_limit.py`](../tools/size_limit.py) enforces the limit on Python
source files only: it scans `aturb`, `packs`, `tools`, `tests` and `clients`,
and only `*.py`. It does not scan `docs/*.md` and it does not scan the browser
assets. The rule in [`AGENTS.md`](../AGENTS.md:29) is written for files in
general, so the tool and the rule do not say the same thing.

This phase treats the tool as the guardrail it is. It changes neither the tool
nor the rule, and it flags three points for a separate project-level review
after T9.01.

- [`aturb/cli.py`](../aturb/cli.py) is 295 lines of 300, so the `view` command
  has five lines to spend and lands the file on exactly 300. Splitting the
  command line into one module per command would improve the separation of
  responsibilities: the parser, the build and check reporting, the evaluation
  reporting and the agent evaluation are four different jobs in one file, and
  the split would give every later command room. It is not done in this phase,
  because splitting it would move the frozen `build`, `check` and `eval`
  behaviour in the same card that adds a command.
- The browser assets are not covered by the tool. The phase applies the rule to
  them by hand, through the card acceptance criteria, and separates the
  rendering from the matrix and camera math so that no asset approaches the
  limit.
- The documentation is not covered by the tool either. This roadmap and the
  task cards grew past 300 lines when the contract details of this phase were
  added, and the review should decide whether the rule applies to documentation
  at all and whether a documentation file has a limit of its own.

No file was split, no option was dropped and no test was removed to make a
number smaller.

## Architectural risks

| Risk                                 | Consequence                   | Control                                                             |
| ------------------------------------ | ----------------------------- | ------------------------------------------------------------------- |
| interface code leaks into the core   | the core stops being neutral  | the viewer lives in `clients/viewer/` only                          |
| the command line overflows           | the size gate fails           | five lines, measured, landing on exactly 300                        |
| a path escapes the workspace         | arbitrary file disclosure     | resolve and check every served path against the root                |
| the server is reachable from outside | an unauthenticated write path | bind to `127.0.0.1` only, check host and origin                     |
| a failed workspace breaks the page   | the viewer shows nothing      | the manifest always loads; the mesh answers with a structured error |
| a credential reaches the browser     | the key leaks to a page       | the key is read from the environment, server-side                   |
| the viewer needs a network           | it stops working offline      | no content delivery network, no bundler, no package                 |
| the mesh is too coarse or too large  | a bad picture or a slow page  | one measured tolerance, the counts shown in the panel               |
| the generation call blocks           | the page appears frozen       | a busy state, a synchronous call, no hidden queue                   |

## Relationship to Phase 10

Phase 9 leaves a viewer that reads one workspace at a time over loopback. A
later phase may compare workspaces, share a viewer between machines or record
viewer sessions, and each of those needs its own decision record. The manifest
of Phase 8 stays the contract between the core and the viewer.
