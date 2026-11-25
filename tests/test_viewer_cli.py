"""Tests for the viewer command line entry point.

The tests open a real workspace over the loopback address and answer two
requests against the bound server. No test leaves the machine.
"""

from __future__ import annotations

import http.client
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from aturb.cli import main
from clients.viewer.server import ViewerServer

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_workspace(root: Path) -> Path:
    """Write a minimal workspace with a manifest and return its folder."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "result.toml").write_text(
        'status = "ok"\npart_id = "part0001"\nstop_reason = "built"\n',
        encoding="utf-8")
    return root


def get(server: ViewerServer, path: str) -> tuple[int, str, bytes]:
    """Answer one GET request against the bound server."""
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), int(port), timeout=10)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        return response.status, response.getheader("Content-Type"), body
    finally:
        connection.close()


def test_the_help_of_the_view_command_names_the_workspace(capsys):
    """The help of the view command names the workspace argument."""
    with pytest.raises(SystemExit) as excinfo:
        main(["view", "--help"])
    out = capsys.readouterr().out
    assert excinfo.value.code == 0
    assert "workspace" in out


def test_a_missing_workspace_returns_2(tmp_path, capsys):
    """A workspace that is not there is a clean error."""
    code = main(["view", str(tmp_path / "absent")])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "workspace" in err


def test_a_workspace_without_a_manifest_returns_2(tmp_path, capsys):
    """A folder without a manifest is a clean error."""
    empty = tmp_path / "empty"
    empty.mkdir()
    code = main(["view", str(empty)])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "result.toml" in err


def test_an_invalid_port_returns_2(tmp_path, capsys, monkeypatch):
    """A port that is not a port number is a clean error."""
    monkeypatch.setenv("ATURB_VIEW_PORT", "notaport")
    workspace = write_workspace(tmp_path / "workspace")
    code = main(["view", str(workspace)])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "ATURB_VIEW_PORT" in err


def test_the_viewer_serves_the_workspace_and_stops_cleanly(tmp_path, capsys,
                                                           monkeypatch):
    """The command prints the address, serves the page and stops cleanly."""
    workspace = write_workspace(tmp_path / "workspace")
    answered: list[tuple[int, str, bytes]] = []
    servers: list[ViewerServer] = []
    original = ViewerServer.serve_forever

    def fake_serve_forever(self: ViewerServer) -> None:
        """Serve in a thread, answer two requests and stop the command."""
        servers.append(self)
        thread = threading.Thread(target=original, args=(self,), daemon=True)
        thread.start()
        try:
            answered.append(get(self, "/"))
            answered.append(get(self, "/api/manifest"))
        finally:
            self.shutdown()
            thread.join(timeout=5)
        raise KeyboardInterrupt

    monkeypatch.setattr(ViewerServer, "serve_forever", fake_serve_forever)

    code = main(["view", str(workspace)])

    out = capsys.readouterr().out
    assert code == 0
    assert len(servers) == 1
    host, port = servers[0].server_address[:2]
    assert host == "127.0.0.1"
    assert f"http://127.0.0.1:{port}/" in out
    status, content_type, body = answered[0]
    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert b"<canvas" in body
    status, _, body = answered[1]
    assert status == 200
    assert b"part0001" in body
    assert servers[0].socket.fileno() == -1


def test_the_other_commands_do_not_import_the_client():
    """The build command never loads the viewer client."""
    script = (
        "import sys\n"
        "from aturb.cli import main\n"
        "try:\n"
        "    main(['build', '--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "loaded = 'clients.viewer' in sys.modules or 'clients' in sys.modules\n"
        "print('CLIENT_IMPORTED' if loaded else 'CLIENT_ABSENT')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    assert result.returncode == 0, result.stderr
    assert "CLIENT_ABSENT" in result.stdout
