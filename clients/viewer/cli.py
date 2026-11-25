"""The command-line entry point of the viewer client.

The client opens a generated workspace in a browser: it resolves the
workspace, binds the loopback-only server of the viewer, prints the address
and blocks until the server stops. The core does not know that this client
exists; the top-level command line imports this module lazily, so the other
commands never load it.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from collections.abc import Callable
from pathlib import Path

from clients.viewer.generate_api import GenerateHandler, GenerateService
from clients.viewer.server import ViewerServer, create_server
from clients.viewer.workspace import WorkspaceError, load_workspace

ADDRESS_LINE = "the viewer is at {url}"
STOP_HINT = "press Ctrl+C to stop the viewer"
STOPPED_LINE = "the viewer stopped"


def start_viewer(
    workspace_path: Path,
    port: int | None = None,
    static_dir: Path | None = None,
    generate_handler: GenerateHandler | None = None,
) -> ViewerServer:
    """Load the workspace and bind the loopback-only viewer server.

    Raises ``WorkspaceError`` when the workspace cannot be read, ``ValueError``
    when the port is not a port number and ``OSError`` when the port cannot
    be bound. The generation service is built here, but it resolves the
    configuration, the pack and the credential only when a request arrives,
    so a read-only viewer needs neither.
    """
    workspace = load_workspace(Path(workspace_path))
    handler = generate_handler if generate_handler is not None else GenerateService()
    return create_server(
        workspace, port=port, static_dir=static_dir, generate_handler=handler)


def run_view_command(
    args: Namespace,
    *,
    server_factory: Callable[..., ViewerServer] = start_viewer,
    serve_fn: Callable[[ViewerServer], None] | None = None,
) -> int:
    """Open the workspace in the viewer and block until the server stops.

    The address is printed before the server blocks, so the user can open it
    in a browser. A workspace that cannot be read, a port that is not a port
    number and a port that is already in use are clean errors: the message
    goes to stderr and the exit code is 2.
    """
    try:
        server = server_factory(Path(args.workspace))
    except (WorkspaceError, ValueError, OSError) as exc:
        print(
            f"the viewer could not open the workspace: {exc}", file=sys.stderr)
        return 2
    print(ADDRESS_LINE.format(url=server.url))
    print(STOP_HINT)
    sys.stdout.flush()
    try:
        if serve_fn is None:
            server.serve_forever()
        else:
            serve_fn(server)
    except KeyboardInterrupt:
        print(STOPPED_LINE)
    finally:
        server.server_close()
    return 0
