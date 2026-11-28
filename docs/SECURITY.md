# Security

This document states what the repository actually enforces today, and what it
does not. There are two separate surfaces: the **build sandbox**, which runs
the part file of a build, and the **loopback viewer server**, which serves one
workspace over HTTP.

## The build sandbox

### What is in place

- Part files pass a static check before running: an import allowlist, banned
  built-in calls, and no dunder attribute access ([`packs/freecad/precheck.py`](../packs/freecad/precheck.py)).
  The FreeCAD runner runs this check before it launches the CAD, so an unsafe or
  syntactically broken part file never reaches a child process.
- Builds run in a separate process with a minimal environment: only an allowlist of
  Windows variables is passed, plus the request path, so API keys, tokens and proxy
  settings are not passed to the part's process.
- A build is killed, with its child processes, after a timeout.
- Every part path and artifact path must stay inside the project folder. A path that
  escapes is refused, and an artifact outside the project is treated as a crash.

### What is NOT guaranteed

- The static check can be bypassed by sufficiently creative code. It is a first
  filter, not a sandbox.
- There is no operating-system-level network block or filesystem jail yet.
- The child process runs as the same operating-system user as the core, so it can
  still read files and open network connections that the user can.
- The static check covers the FreeCAD pack's part files only.

## The loopback viewer server

The viewer is a local, single-user tool. It serves one workspace over HTTP on
the loopback address and nothing else.

### What is in place

- **The bind is loopback-only.** The server binds to `127.0.0.1` and never to
  `0.0.0.0`. Any other host is refused before the socket is opened
  ([`clients/viewer/server.py`](../clients/viewer/server.py)). The port comes
  from the argument, from the `ATURB_VIEW_PORT` environment variable or from
  the operating system.
- **The address headers are checked against the bound port.** Every mutating
  request must carry a `Host` header that names `127.0.0.1:<port>` or
  `localhost:<port>` for the port the server actually bound to. The `Origin`
  header is optional, and when it is present it must name the same address with
  the `http` scheme. A missing `Host`, a foreign host, a foreign scheme, a
  different port on the same address, a path, a query, a fragment, a userinfo
  part (`user:password@host`) and the literal `Origin: null` are all refused
  with `403`. The check happens **before the body is read**, so a refused
  request never reaches a service and never leaves a body on the socket.
- **The guard chain of a mutating request is fixed.** The order is
  `Host`/`Origin` -> the endpoint is enabled -> `Content-Length` -> the JSON
  body -> the service lock. A request that fails any step is refused with the
  status of that step and the body is never read.
- **The body limit is one number everywhere.** `MAX_BODY_BYTES = 65_536` lives
  in [`clients/viewer/http_utils.py`](../clients/viewer/http_utils.py) and every
  endpoint uses it. A missing `Content-Length` is `411`, a `Content-Length`
  that is not a number or is negative is `400`, and a body larger than the
  limit is `413`. The body is never read on a refusal.
- **The credential never reaches the browser.** The provider key is read from
  the environment variable the configuration names and stays on the server.
  `SafeModelClient` removes the credential from every message it returns, and
  `sanitize_message()` removes both the credential and the absolute paths of
  the host from every message that is written into a manifest or an answer.
  The HTTP responses and the manifests carry no path of the host.
- **Every path is contained.** A workspace artifact is named by a kind, never
  by a path, and the declared relative path is resolved against the workspace
  root and refused unless it stays inside it
  ([`clients/viewer/workspace.py`](../clients/viewer/workspace.py)). A browser
  asset is one file name: a separator, a parent component, an unknown
  extension, a missing file and an escaping symbolic link are all refused with
  `404`.
- **The responses are hardened.** Every response carries
  `X-Content-Type-Options: nosniff`. Every string that comes from a manifest
  or from the server reaches the page through `textContent` only, so a manifest
  cannot inject markup; the browser assets contain no `innerHTML`, no
  `outerHTML` and no `document.write`.
- **One mutating request runs at a time.** The generation, the edit, the
  rollback and the assembly services share one lock, so they never race, and a
  busy service answers `409`.

### What is NOT guaranteed

- The viewer has no authentication, no multi-user hosting and no cloud
  deployment. It is a local tool that runs as the same operating-system user
  as the core.
- The loopback bind and the address checks stop a request from another page
  and a request from another machine. They are not a sandbox for the code the
  agent writes.
- The viewer serves the workspace it was given. It does not decide what may be
  in that workspace.

## Persistence

The workspace files are written through
[`aturb/workspace/io.py`](../aturb/workspace/io.py): a temporary file in the
destination folder, `flush()`, `os.fsync()`, then `os.replace()`.

**This is atomicity for one file.** `os.replace()` is atomic on the file it
replaces, so a reader never sees a half-written file. It is **not** a
transaction over several files and it is **not** a database: a reader can
still see a workspace whose several files were written at different moments,
and there is no rollback across files.

## Planned

- Run builds inside a container (or an equivalent OS sandbox) before any untrusted
  user can submit requests.
