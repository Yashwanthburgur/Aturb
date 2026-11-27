"""The command-line entry point of the viewer client.

The client opens a generated workspace in a browser: it resolves the
workspace, binds the loopback-only server of the viewer, prints the address
and blocks until the server stops. The core does not know that this client
exists; the top-level command line imports this module lazily, so the other
commands never load it.
"""

from __future__ import annotations

import inspect
import sys
import threading
from argparse import Namespace
from collections.abc import Callable
from pathlib import Path

from clients.viewer.assembly_edit_api import AssemblyEditService
from clients.viewer.edit_api import EditHandler, EditService, RollbackHandler
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
    edit_handler: EditHandler | None = None,
    rollback_handler: RollbackHandler | None = None,
    assembly_edit_service: AssemblyEditService | None = None,
    config_path: Path | None = None,
) -> ViewerServer:
    """Load the workspace and bind the loopback-only viewer server.

    Raises ``WorkspaceError`` when the workspace cannot be read, ``ValueError``
    when the port is not a port number and ``OSError`` when the port cannot
    be bound. The generation and the edit services are built here, but they
    resolve the configuration, the pack and the credential only when a request
    arrives, so a read-only viewer needs neither. Every service shares one
    lock, so a generation, an edit and a rollback never race.

    The path of the configuration is given to every service, so the viewer
    uses the file of the command line and not the default of the machine.
    """
    workspace = load_workspace(Path(workspace_path))
    handler = (generate_handler if generate_handler is not None
               else GenerateService(config_path=config_path))
    service = EditService(lock=_shared_lock(handler), config_path=config_path)
    editor = edit_handler if edit_handler is not None else service.edit
    roller = rollback_handler if rollback_handler is not None else service.rollback
    assembly = assembly_edit_service or AssemblyEditService(
        workspace.root, config_path, lock=_shared_lock(handler))
    return create_server(
        workspace, port=port, static_dir=static_dir, generate_handler=handler,
        edit_handler=editor, rollback_handler=roller,
        assembly_edit_service=assembly)


def _shared_lock(handler: object) -> threading.Lock:
    """Return the lock of the generation service, so the two never race."""
    lock = getattr(handler, "_lock", None)
    return lock if lock is not None else threading.Lock()


def _start_server(server_factory: Callable[..., ViewerServer], workspace: Path,
                  config_path: Path | None) -> ViewerServer:
    """Start the server, with the configuration path when the factory takes it.

    A factory of an older caller takes only the workspace, so the path of the
    configuration is given only to a factory that names it.
    """
    try:
        parameters = inspect.signature(server_factory).parameters
    except (TypeError, ValueError):
        parameters = {}
    takes_path = "config_path" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values())
    if takes_path:
        return server_factory(workspace, config_path=config_path)
    return server_factory(workspace)


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
    config_path = Path(args.config) if getattr(args, "config", None) else None
    try:
        server = _start_server(
            server_factory, Path(args.workspace), config_path)
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
