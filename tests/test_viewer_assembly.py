"""Tests for the assembly command and the assembly workspace of the viewer.

The stub pack builds every part, so the whole pipeline runs without a CAD.
The viewer is served over the loopback address and every answer is read back
as JSON.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from build123d import Box, Compound, Location, export_step

from aturb.assembly.build import build_assembly
from aturb.cli import main
from aturb.packs import default_packs_root, load_runner
from clients.viewer.mesh import tessellate_step
from clients.viewer.server import create_server, serve_in_thread
from clients.viewer.workspace import load_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "clients" / "viewer" / "static"
FIXTURE = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"
TOUCHED_ASSETS = ("assembly.js", "index.html", "inspector.js")
JS_ASSETS = ("assembly.js", "inspector.js")
CONFIG = 'active_pack = "stub"\n[packs.stub]\n[timeouts]\nbuild_s = 60\n'
PART_TEXT = "# stub part\n"

MANIFEST = """
assembly_id = "asm0001"
name = "Two plates"

[[components]]
name = "plate"
part_id = "plt0001"
position = [0.0, 0.0, 0.0]

[[components]]
name = "plate_top"
part_id = "plt0002"
position = [0.0, 0.0, 6.0]

[[mates]]
part_a = "plate"
part_b = "plate_top"
min_clearance_mm = 0.5
max_clearance_mm = 1.5
"""


def _runner():
    """Return the runner of the stub pack."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def _project(tmp_path: Path, top: tuple[float, float, float] = (0.0, 0.0, 6.0)) -> Path:
    """Write a project with two stub parts and one assembly manifest."""
    project = tmp_path / "project"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001_base_plate.stub").write_text(PART_TEXT, encoding="utf-8")
    (parts / "plt0002_top_plate.stub").write_text(PART_TEXT, encoding="utf-8")
    assemblies = project / "assemblies"
    assemblies.mkdir(parents=True)
    manifest = MANIFEST.replace(
        "position = [0.0, 0.0, 6.0]", f"position = [{top[0]}, {top[1]}, {top[2]}]")
    (assemblies / "asm0001.toml").write_text(manifest, encoding="utf-8")
    return project


def _config(tmp_path: Path) -> Path:
    """Write a configuration that names the stub pack."""
    path = tmp_path / "aturb.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return path


def _manifest_path(project: Path) -> Path:
    """Return the manifest of the assembly of a project."""
    return project / "assemblies" / "asm0001.toml"


def _assembly_dir(project: Path) -> Path:
    """Return the output folder of the assembly of a project."""
    return project / "out" / "assemblies" / "asm0001"


@contextlib.contextmanager
def _serving(workspace):
    """Serve a workspace over loopback and stop the server afterwards."""
    server = create_server(workspace, port=0)
    thread = serve_in_thread(server)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(server, path: str) -> tuple[int, dict]:
    """Answer one GET request and return the status and the body."""
    host, port = server.server_address[:2]
    connection = http.client.HTTPConnection(str(host), int(port), timeout=20)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_the_assemble_command_reports_a_clean_assembly(tmp_path, capsys):
    """A clean assembly exits with 0 and prints one line about it."""
    project = _project(tmp_path)

    code = main(["assemble", str(project), str(_manifest_path(project)),
                 "--config", str(_config(tmp_path))])
    out = capsys.readouterr().out

    assert code == 0
    assert out.startswith("ok asm0001 components=2 interference=no step=")
    assert "out/assemblies/asm0001/asm0001.step" in out
    assert (_assembly_dir(project) / "asm0001.step").is_file()


def test_the_assemble_command_reports_a_clashing_assembly(tmp_path, capsys):
    """A clashing assembly exits with 1 and says why."""
    project = _project(tmp_path, top=(0.0, 0.0, 0.0))

    code = main(["assemble", str(project), str(_manifest_path(project)),
                 "--config", str(_config(tmp_path))])
    out = capsys.readouterr().out

    assert code == 1
    assert out.startswith("failed asm0001: ")
    assert "interfere" in out


def test_the_assemble_command_refuses_a_missing_manifest(tmp_path, capsys):
    """A manifest that is not there exits with 2."""
    project = _project(tmp_path)

    code = main(["assemble", str(project),
                 str(project / "assemblies" / "ghost.toml"),
                 "--config", str(_config(tmp_path))])
    out = capsys.readouterr().out

    assert code == 2
    assert "ghost.toml" in out


def test_a_multi_solid_step_tessellates_into_one_mesh(tmp_path):
    """The tessellation of a compound holds the vertices of both solids."""
    first = Box(10, 10, 10)
    second = Box(10, 10, 10).moved(Location((30, 0, 0)))
    path = tmp_path / "compound.step"
    export_step(Compound([first, second]), str(path))

    mesh = tessellate_step(path)

    assert mesh.vertex_count > 0
    assert mesh.triangle_count > 0
    assert len(mesh.positions) == mesh.vertex_count * 3
    assert len(mesh.indices) == mesh.triangle_count * 3
    xs = mesh.positions[0::3]
    assert min(xs) < -4.0
    assert max(xs) > 34.0


def test_the_viewer_serves_the_assembly_payload(tmp_path):
    """The manifest of an assembly workspace carries the assembly payload."""
    project = _project(tmp_path)
    result = build_assembly(project, _manifest_path(project), _runner())
    assert result.status == "ok", result.error
    workspace = load_workspace(_assembly_dir(project))

    with _serving(workspace) as server:
        status, payload = _get(server, "/api/manifest")

    assert status == 200
    assembly = payload["assembly"]
    assert assembly is not None
    assert assembly["assembly_id"] == "asm0001"
    assert assembly["assembly_name"] == "Two plates"
    assert assembly["status"] == "ok"
    assert assembly["component_count"] == 2
    assert assembly["has_interference"] is False
    assert assembly["all_mates_ok"] is True
    assert assembly["total_volume"] > 0.0
    assert len(assembly["bbox_size"]) == 3
    assert len(assembly["pairs"]) == 1
    assert assembly["pairs"][0]["part_a"] == "plate"
    assert str(project) not in json.dumps(payload)


def test_the_viewer_serves_the_mesh_of_the_whole_assembly(tmp_path):
    """The mesh of an assembly workspace holds both components."""
    project = _project(tmp_path)
    result = build_assembly(project, _manifest_path(project), _runner())
    assert result.status == "ok", result.error
    workspace = load_workspace(_assembly_dir(project))

    with _serving(workspace) as server:
        status, payload = _get(server, "/api/mesh")

    assert status == 200
    assert payload["vertex_count"] > 0
    assert payload["triangle_count"] > 0
    assert len(payload["positions"]) == payload["vertex_count"] * 3
    assert len(payload["indices"]) == payload["triangle_count"] * 3
    zs = payload["positions"][2::3]
    assert min(zs) < -2.0
    assert max(zs) > 8.0


def test_the_history_of_an_assembly_workspace_is_not_editable(tmp_path):
    """An assembly workspace has no history and cannot be edited."""
    project = _project(tmp_path)
    result = build_assembly(project, _manifest_path(project), _runner())
    assert result.status == "ok", result.error
    workspace = load_workspace(_assembly_dir(project))

    with _serving(workspace) as server:
        status, payload = _get(server, "/api/history")

    assert status == 200
    assert payload == {"has_history": False, "active_revision": None,
                       "editable": False, "revisions": []}


def test_a_single_part_workspace_has_no_assembly(tmp_path):
    """A plain workspace still answers with no assembly at all."""
    folder = tmp_path / "workspace"
    folder.mkdir()
    (folder / "part.step").write_bytes(FIXTURE.read_bytes())
    (folder / "result.toml").write_text(
        'status = "ok"\npart_id = "part0001"\nstep_file = "part.step"\n',
        encoding="utf-8")
    workspace = load_workspace(folder)

    with _serving(workspace) as server:
        status, payload = _get(server, "/api/manifest")

    assert status == 200
    assert payload["assembly"] is None
    assert payload["status"] == "ok"


def test_the_touched_browser_assets_are_clean():
    """Every touched browser asset passes node and the hygiene rules."""
    if shutil.which("node") is None:
        pytest.skip("node is not on this machine")
    for name in TOUCHED_ASSETS:
        path = STATIC_DIR / name
        text = path.read_text(encoding="utf-8")
        assert "innerHTML" not in text, name
        assert "http://" not in text and "https://" not in text, name
        assert "\t" not in text, name
        assert text.endswith("\n"), name
        assert len(text.splitlines()) <= 300, name
        for number, line in enumerate(text.splitlines(), start=1):
            assert line == line.rstrip(), f"{name}:{number} has trailing space"
    for name in JS_ASSETS:
        result = subprocess.run(
            ["node", "--check", str(STATIC_DIR / name)],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
