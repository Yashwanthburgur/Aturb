"""The harness that runs inside the CAD must never import the core package."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner
from aturb.verify.step import load_step
from packs.freecad.precheck import precheck

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = REPO_ROOT / "packs" / "freecad" / "harness" / "build_part.py"
CORE = REPO_ROOT / "aturb"
BUILD_TIMEOUT_S = 60  # starting default

PART_SOURCE = '''"""A part file that uses the injected helper."""

import FreeCAD as App
import Part

LENGTH_MM = 120.0
WIDTH_MM = 60.0
THICKNESS_MM = 5.0
FILLET_RADIUS_MM = 3.0


def build(doc):
    """Build a plate and fillet the corner edges the helper selected."""
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.addGeometry(
        Part.LineSegment(App.Vector(-60, -30, 0), App.Vector(60, -30, 0)), False)
    sketch.addGeometry(
        Part.LineSegment(App.Vector(60, -30, 0), App.Vector(60, 30, 0)), False)
    sketch.addGeometry(
        Part.LineSegment(App.Vector(60, 30, 0), App.Vector(-60, 30, 0)), False)
    sketch.addGeometry(
        Part.LineSegment(App.Vector(-60, 30, 0), App.Vector(-60, -30, 0)), False)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = THICKNESS_MM
    doc.recompute()

    edges = helper.corner_edges(body.Tip.Shape, LENGTH_MM, WIDTH_MM)
    helper.assert_count(edges, 4, "vertical corner edges")

    fillet = body.newObject("PartDesign::Fillet", "Fillet")
    fillet.Base = (pad, edges)
    fillet.Radius = FILLET_RADIUS_MM
    doc.recompute()
    return body
'''

CORE_PROBE = (
    "import sys\n"
    "import aturb\n"
    "leaked = [n for n in sys.modules\n"
    "          if n.split('.')[0] in ('packs', 'freecad', 'FreeCAD')]\n"
    "assert not leaked, leaked\n"
    "assert not hasattr(aturb, 'helper')\n"
    "assert 'packs.freecad.helper.select' not in sys.modules\n"
    "print('CORE_ISOLATED')\n"
)


def make_runner():
    """Load the real FreeCAD runner with the local config."""
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    return load_runner("freecad", cfg, default_packs_root())


def test_harness_never_imports_aturb():
    """No import of aturb or any aturb.* module in the harness."""
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("aturb"), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("aturb"), node.module


def test_the_harness_resolves_the_helper_of_the_pack():
    """The harness loads the helper of the pack by path, under the name helper.

    The harness imports FreeCAD and starts a build when it is imported, so its
    constants are read from the source instead. Only the assignments at the top
    of the file are evaluated, and they use nothing but os and __file__.
    """
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    namespace = {"os": os, "__file__": str(HARNESS)}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         str(HARNESS), "exec"), namespace)
    assert namespace["HELPER_NAME"] == "helper"
    helper_path = Path(namespace["HELPER_MODULE"])
    assert helper_path == REPO_ROOT / "packs" / "freecad" / "helper" / "select.py"
    assert helper_path.is_file()


def test_the_core_never_imports_the_pack():
    """No file of the core imports the pack, the helper or the CAD."""
    for path in sorted(CORE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in (
                        "packs", "freecad", "FreeCAD")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in ("packs", "freecad", "FreeCAD")


def test_the_helper_is_not_reachable_from_the_core():
    """Importing the core pulls in no pack module and exposes no helper."""
    proc = subprocess.run([sys.executable, "-c", CORE_PROBE], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=BUILD_TIMEOUT_S)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CORE_ISOLATED" in proc.stdout


@pytest.mark.freecad
def test_a_part_file_that_uses_the_helper_builds(tmp_path):
    """A part file that uses the injected helper builds real geometry."""
    assert precheck(PART_SOURCE) == ("ok", [])

    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "zzz0001_helper.py").write_text(PART_SOURCE, encoding="utf-8")

    request = BuildRequest(
        project_root=str(project),
        part_id="zzz0001",
        language="python-freecad",
        timeout_s=BUILD_TIMEOUT_S,
    )
    result = make_runner().build(request)

    assert result.status == "ok", result.error_text
    step = project / result.artifacts["step"]
    assert step.is_file()
    assert step.stat().st_size > 0

    model = load_step(step)
    assert model.is_single_solid
    assert model.is_valid
    # Measured in-session on FreeCAD 1.0.1: the plain plate is 36000 mm^3 and
    # the four 3 mm corner fillets remove 38.628331 mm^3 of it.
    assert abs(model.volume - 35961.371669) <= 0.01
    size = model.bbox_size
    assert abs(size.X - 120.0) <= 0.01
    assert abs(size.Y - 60.0) <= 0.01
    assert abs(size.Z - 5.0) <= 0.01
