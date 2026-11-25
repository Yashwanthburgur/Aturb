# Phase 9 task cards — live 3D STEP viewer and interactive UI

These cards implement [`docs/PHASE9_ROADMAP.md`](PHASE9_ROADMAP.md) and
[`docs/adr/0011-live-step-viewer-and-client-boundary.md`](adr/0011-live-step-viewer-and-client-boundary.md).
Every card is small, file-scoped and gate-checked. The runner contract, the
answer schema, the evaluation records, the scoring rule and the `result.toml`
schema remain frozen.

Rules every card inherits:

- The core stays CAD-neutral, language-neutral and interface-neutral; the
  viewer, the server and the browser assets live under `clients/viewer/`.
- No new dependency, no Node.js, no npm, no bundler, no content delivery network.
- The server binds to `127.0.0.1` only and serves only declared files.
- Every implementation file is at most 300 lines, including the `.html`, `.css`
  and `.js` assets, which `tools/size_limit.py` does not check.
- Every chosen default is marked `# starting default`; no card stages, commits
  or pushes.
- Each card states what it guarantees — CAD neutrality, loopback-only
  security, workspace containment, artifact integrity, server-side credentials
  and offline-first rendering — and leaves the internal shape to the card.

## Summary

| Card  | FILES                                                                                                                                                                                             | DO EXACTLY (summary)                                                            | COMMIT                                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| T9.01 | `docs/PHASE9_ROADMAP.md`, `docs/PHASE9_TASKS.md`, `docs/adr/0011-live-step-viewer-and-client-boundary.md`, `docs/adr/README.md`                                                                   | Record the architecture, the verified facts and the card sequence               | `docs(viewer): plan the live STEP viewer and the client boundary` |
| T9.02 | `clients/viewer/__init__.py`, `clients/viewer/workspace.py`, `clients/viewer/mesh.py`, `tests/test_viewer_workspace.py`, `tests/test_viewer_mesh.py`                                              | Load a manifest safely and tessellate its STEP with the verified call           | `feat(viewer): load a workspace safely and tessellate its STEP`   |
| T9.03 | `clients/viewer/server.py`, `tests/test_viewer_server.py`                                                                                                                                         | Serve the page, manifest, mesh, declared files and browser assets over loopback | `feat(viewer): serve the workspace over loopback only`            |
| T9.04 | `clients/viewer/static/index.html`, `clients/viewer/static/viewer.css`, `clients/viewer/static/viewer.js`, `clients/viewer/static/math3d.js`, `clients/viewer/static/inspector.js`                | Draw the part, the axes and the box, and fill the facts panel                   | `feat(viewer): draw the part in a zero-build WebGL viewport`      |
| T9.05 | `clients/viewer/cli.py`, `aturb/cli.py`, `pyproject.toml`, `tests/test_viewer_cli.py`                                                                                                             | Add `aturb view <workspace>` in exactly five lines of the CLI                   | `feat(cli): add the aturb view command`                           |
| T9.06 | `clients/viewer/generate_api.py`, `clients/viewer/server.py`, `clients/viewer/cli.py`, `clients/viewer/static/prompt.js`, `clients/viewer/static/index.html`, `tests/test_viewer_generate_api.py` | Add the bound-port-checked prompt endpoint and the prompt panel                 | `feat(viewer): generate a new part from the page`                 |
| T9.07 | `docs/PHASE9_BASELINE.md`; git-ignored viewer output                                                                                                                                              | Record one live interactive run with honest measurements                        | `docs(viewer): record the Phase 9 live viewer baseline`           |

## T9.01 — Roadmap, task cards and ADR-0011

GOAL: Record the viewer architecture, its verified facts and the card sequence.

FILES (only these): `docs/PHASE9_ROADMAP.md`, `docs/PHASE9_TASKS.md`,
`docs/adr/0011-live-step-viewer-and-client-boundary.md`, `docs/adr/README.md`

DO EXACTLY:

1. Place the viewer, the server and the browser assets outside the core, under
   `clients/viewer/`, and state that the core stays CAD-neutral,
   language-neutral and interface-neutral.
2. Record the measured facts: the installed `build123d` version, the verified
   `StepModel.shape` tessellation method, signature and return structure, the
   scanned directories, tokens and extensions of both lint tools, the installed
   dependencies, and the measured `aturb/cli.py` line count and headroom.
3. Decide the zero-build, offline-safe WebGL viewport and record the trade-off
   against an external content delivery network.
4. Decide the two stages — the read-only live viewer, then the interactive
   prompt-to-3D endpoint — with the non-goals of both.
5. Decide the loopback binding, the declared-file and path-containment rules,
   the local origin and host check and the server-side credential.
6. Fix the command-line line-budget strategy against the measured count.
7. Define T9.01 through T9.07 and index ADR-0011 in the existing format.

DO NOT: change implementation; add a dependency; name a backend in ADR-0011;
assume a tessellation method that was not verified; change an earlier baseline.

ACCEPTANCE: the file-size, agnosticism and lint gates pass; every one of the
four files is at most 300 lines; ADR-0011 names only verified facts.

EVIDENCE: the four documents, their diff and the measured facts.

COMMIT: `docs(viewer): plan the live STEP viewer and the client boundary`

DEPENDS ON: Phase 8.

## T9.02 — Neutral STEP tessellation and safe workspace loader

GOAL: Read a generated workspace safely and mesh its exported STEP.

FILES (only these): `clients/viewer/__init__.py`, `clients/viewer/workspace.py`,
`clients/viewer/mesh.py`, `tests/test_viewer_workspace.py`,
`tests/test_viewer_mesh.py`

DO EXACTLY:

1. Add a loader that reads `result.toml` with the standard-library TOML reader
   and returns the manifest fields and the three declared artifact paths.
2. Support a manifest from a failed generation: an empty or absent `step_file`,
   `part_file` or `native_file` yields no artifact for that kind, the other
   manifest fields are still loaded, and a malformed manifest is reported as an
   error rather than raised.
3. Resolve every declared path against the workspace root and refuse it unless
   the resolved path is inside the resolved root. Refuse `..`, an absolute path
   and a symbolic link that escapes the root.
4. Add a mesh builder that calls the core's `load_step()` and then the verified
   `model.shape.tessellate(tolerance, angular_tolerance)` call, and returns the
   vertex positions, the triangle indices and the two counts.
5. Mark the tessellation tolerance `0.1` millimetres as `# starting default`.
6. Test the loader on a written workspace, on a manifest whose artifacts are
   empty or absent, the three refusals, the mesh on the committed fixture, the
   counts, the index range and the empty-mesh refusal.
7. Add a real-backend test, marked with the existing backend marker, that
   builds a part, exports its STEP and tessellates it into a non-empty mesh.

DO NOT: import a backend; add a dependency; write a mesh file into the
repository; change `aturb/verify/step.py`; guess a tessellation call; use a
network or a live model.

ACCEPTANCE: the new tests, lint, file-size and agnosticism gates pass; every
new file is at most 290 lines.

EVIDENCE: targeted test output, the static gates and the four-file diff.

COMMIT: `feat(viewer): load a workspace safely and tessellate its STEP`

DEPENDS ON: T9.01.

## T9.03 — Loopback-only read-only viewer server

GOAL: Serve the open workspace over loopback-only HTTP.

FILES (only these): `clients/viewer/server.py`, `tests/test_viewer_server.py`

DO EXACTLY:

1. Add a server that binds to `127.0.0.1` and never to `0.0.0.0`, using the
   standard-library HTTP server only.
2. Serve `GET /` with the page, `GET /api/manifest` with the measured facts as
   JSON, `GET /api/mesh` with the mesh as JSON and `GET /api/files/<kind>`
   with the declared artifact.
3. Serve the browser assets bundled under `clients/viewer/static/` with the
   MIME type their extension implies, and refuse an unknown asset or one that
   leaves that directory with `404`.
4. Accept only the three declared kinds and refuse every other value. Never
   take a path from the request.
5. Resolve and check every served path against the workspace root before
   reading it.
6. Choose the port from the operating system by default and allow the
   `ATURB_VIEW_PORT` environment variable to pin it. Mark the default as
   `# starting default`.
7. When the workspace has no usable STEP file, answer `200` for `/` and
   `/api/manifest`, and answer `404` for an absent artifact and `422` for one
   that cannot be meshed, always with a structured JSON body and never with an
   unhandled server error.
8. Test the loopback binding, the read-only routes, the serving of the browser
   assets with their MIME types, the refusal of an unknown kind, of an escaping
   asset path, of a path that leaves the workspace and of an undeclared file,
   and the `404` and `422` answers of a workspace without a usable STEP file.

DO NOT: bind to `0.0.0.0`; add a dependency; add a mutating route; write into
the workspace; serve a path from the request; add authentication.

ACCEPTANCE: the new tests, lint, file-size and agnosticism gates pass; the
server file is at most 290 lines.

EVIDENCE: targeted test output, the static gates and the two-file diff.

COMMIT: `feat(viewer): serve the workspace over loopback only`

DEPENDS ON: T9.02.

## T9.04 — Zero-build offline 3D viewport and engineering inspector

GOAL: Show the geometry and the measured facts in a browser with no build step
and no network.

FILES (only these): `clients/viewer/static/index.html`,
`clients/viewer/static/viewer.css`, `clients/viewer/static/viewer.js`,
`clients/viewer/static/math3d.js`, `clients/viewer/static/inspector.js`

DO EXACTLY:

1. Write a self-contained page that loads only its own local assets. No
   content delivery network, no external font, no external script.
2. Draw the mesh with the WebGL context of the browser: a shaded view with
   lighting, and an edge or wireframe view.
3. Add orbit on a drag, pan on a modifier drag and zoom on the wheel, with the
   camera framed on the mesh. Keep the 4x4 matrix, camera and normal math in
   `math3d.js`, so `viewer.js` holds only the WebGL rendering.
4. Draw the three axes and the bounding box of the mesh.
5. Fill the panel with the measured facts of the manifest: the status, the stop
   reason, the attempts, the usage, the build outcome, the advisory findings,
   the validity, the solidity, the volume, the bounding-box size and the holes.
6. Add the three artifact download links, pointing at the declared kinds.
7. Reserve an empty container element for the prompt panel that T9.06 fills.
8. Derive the shading normals and the bounding box in the browser from the
   mesh payload.
9. When `/api/mesh` reports that there is no usable STEP file, show a clear
   empty state in the viewport and still render the manifest status, the error,
   the advisory findings and the downloads that do exist.

DO NOT: add a dependency, a bundler, a package manager or a content delivery
network; use a framework; exceed 300 lines in any asset; change the server.

ACCEPTANCE: every asset is at most 300 lines, has no trailing whitespace and
no tab character, and ends with a newline; the page loads with the network
disconnected; the static gates pass.

EVIDENCE: the five assets, their line counts and the static gates.

COMMIT: `feat(viewer): draw the part in a zero-build WebGL viewport`

DEPENDS ON: T9.03.

## T9.05 — Thin command-line entry point

GOAL: Open a workspace with `aturb view <workspace>` without changing any
existing command.

FILES (only these): `clients/viewer/cli.py`, `aturb/cli.py`, `pyproject.toml`,
`tests/test_viewer_cli.py`

DO EXACTLY:

1. Add the client entry point that resolves the workspace, starts the server
   on `127.0.0.1`, prints the address and blocks until the server stops.
2. Add exactly five lines to `aturb/cli.py`: the `view` parser, its workspace
   argument, the dispatch branch, a lazy import of the client entry point and
   the delegation. The file lands on exactly 300 lines.
3. Place the dispatch branch immediately after the argument parsing and before
   the configuration block, because the `view` parser has no `--config` option
   and the client resolves the configuration itself.
4. Keep the import inside the branch, so `build`, `check` and `eval` never
   import the client package and keep their printed lines and exit codes.
5. Add `clients` to the wheel package list in `pyproject.toml` and verify that
   the static files under `clients/viewer/static/` ship as package data. Add no
   dependency.
6. Test that `aturb view --help` works, that a missing workspace exits 2, that
   the server binds to `127.0.0.1`, and that existing commands are unchanged.

DO NOT: add a sixth line to `aturb/cli.py`; add a `--port` flag; change the
existing CLI tests; change the printed lines or the exit codes of `build`,
`check` or `eval`; add a dependency.

ACCEPTANCE: `aturb/cli.py` is exactly 300 lines; the new tests, the existing
CLI tests, lint, file-size and agnosticism gates pass; `aturb view --help`
works.

EVIDENCE: the measured line count, the targeted test output, the static gates
and the four-file diff.

COMMIT: `feat(cli): add the aturb view command`

DEPENDS ON: T9.04.

## T9.06 — Interactive prompt-to-3D endpoint and prompt panel

GOAL: Let the user ask for a part from the page and watch it appear.

FILES (only these): `clients/viewer/generate_api.py`, `clients/viewer/server.py`,
`clients/viewer/cli.py`, `clients/viewer/static/prompt.js`,
`clients/viewer/static/index.html`, `tests/test_viewer_generate_api.py`

DO EXACTLY:

1. Mount `POST /api/generate` in `server.py`, which takes a natural-language
   requirement and answers with the new workspace identity, the status and the
   stop reason.
2. Check the `Host` header against `127.0.0.1:<port>` and `localhost:<port>`
   for the port the server actually bound to, and the `Origin` header, when
   present, against `http://127.0.0.1:<port>` and `http://localhost:<port>` for
   that same port. Refuse any other host, scheme or port with `403`.
3. Wire the configuration and the model-client factory into the server through
   `cli.py`, so the endpoint resolves the pack, runner and settings.
4. Call the existing expectation-free `generate_part()` and
   `write_generate_manifest()` into a fresh timestamped workspace, then switch
   the open workspace to it.
5. Read the provider credential from the environment variable the
   configuration names, on the server only. Never send it to the browser, never
   return it and never print it.
6. Add the prompt panel in `prompt.js` and load it from `index.html`: a text
   field, a submit button, a busy state while the call runs, and an error line
   when the call fails.
7. After a successful call, re-read the manifest and the mesh and update the
   viewport and the panel without a page reload.
8. Test with a fake client and the stub pack: success, an empty requirement and
   a failed generation. Test the refusal of a foreign host, of a foreign
   scheme and of a wrong port on `127.0.0.1` and on `localhost`, in the `Host`
   header and in the `Origin` header. No live call.

DO NOT: create a task, an answer or an expectation; score anything; show a
correctness claim; send a credential to the browser; add authentication, a
queue, a background job or streaming; change the generation service.

ACCEPTANCE: the new tests, lint, file-size and agnosticism gates pass; every
new file is at most 290 lines; no test makes a network or live-model call.

EVIDENCE: targeted test output, the static gates and the six-file diff.

COMMIT: `feat(viewer): generate a new part from the page`

DEPENDS ON: T9.05.

## T9.07 — Live verification and the Phase 9 baseline

GOAL: Record one real interactive run of the viewer after the implementation
cards have been reviewed.

FILES (only these): `docs/PHASE9_BASELINE.md`; git-ignored viewer output and
screenshots under `evals/tmp/phase9_baseline/`

DO EXACTLY:

1. Run `aturb view <workspace>` once on a generated workspace, open the page
   and exercise the viewport: orbit, pan, zoom, the shaded and edge views, the
   axes, the bounding box, the facts panel and the three downloads.
2. Record the date, the command, the workspace, the bound address, the measured
   vertex and triangle counts, the measured timings of the manifest read, the
   tessellation and the first page load, and the browser used.
3. Exercise the prompt panel once with a self-contained requirement and record
   the new workspace, its status, its stop reason and its measured counts.
4. Capture a screenshot of the rendered page for the workspace that was opened
   and one for the workspace the prompt produced, each showing the 3D viewport
   and the measured facts panel. Save them in the git-ignored
   `evals/tmp/phase9_baseline/` folder and name every file and what it shows
   in the baseline.
5. Record the refusals that were observed: a path that leaves the workspace, an
   unknown kind, an escaping asset path and a foreign origin or port.
6. State that one run is not a benchmark, that a model call is not
   deterministic and that the viewer is a local single-user tool.

DO NOT: run this card with the offline implementation cards; fabricate a
measurement, a count or a timing; expose a credential; commit a screenshot or
any other binary; modify the committed task set; claim a general correctness or
autonomy result.

ACCEPTANCE: the baseline holds the exact commands, the measured counts, the
measured timings, the observed refusals, the screenshot file names and the
qualifications.

EVIDENCE: the baseline, the git-ignored output workspace and the screenshots.

COMMIT: `docs(viewer): record the Phase 9 live viewer baseline`

DEPENDS ON: reviewed and accepted T9.06.
