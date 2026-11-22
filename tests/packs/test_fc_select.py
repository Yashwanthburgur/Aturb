"""Tests for the FreeCAD selection helper, measured in the real CAD.

The helper runs inside the CAD, so the test sends a small script to the CAD
executable of the local configuration and reads the result the script prints.
"""

from __future__ import annotations

import ast
import json
import math
import subprocess
from pathlib import Path

import pytest

from aturb.config import load_config, pack_settings
from packs.freecad.helper import select

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = REPO_ROOT / "packs" / "freecad" / "helper" / "select.py"
TIMEOUT_S = 120  # starting default
RESULT_PREFIX = "RESULT: "

SCRIPT = '''import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(REPO_ROOT_PLACEHOLDER)
sys.path.insert(0, str(ROOT))

import FreeCAD as App
from packs.freecad.helper import select

part = ROOT / "projects" / "demo" / "parts" / "plt0001_base_plate.py"
spec = importlib.util.spec_from_file_location("demo_part", part)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

doc = App.newDocument("SelectTest")
obj = module.build(doc)
doc.recompute()
shape = obj.Tip.Shape

corners = select.corner_edges(shape, 120.0, 60.0)
circles = select.circular_edges(shape, 5.0)
top = select.top_faces(shape)
bottom = select.bottom_faces(shape)
try:
    select.assert_radius(shape, circles, 3.0)
    radius_failure = ""
except AssertionError as exc:
    radius_failure = str(exc)

print("RESULT: " + json.dumps({
    "edge_count": len(shape.Edges),
    "vertical": select.vertical_edges(shape),
    "corners": corners,
    "corner_points": [select.edge_points(shape, n) for n in corners],
    "circles": circles,
    "circle_lengths": [select.edge_length(shape, n) for n in circles],
    "circle_types": [select.edge_type(shape, n) for n in circles],
    "radius_failure": radius_failure,
    "face_count": len(shape.Faces),
    "top": top,
    "bottom": bottom,
    "top_area": [select.face_area(shape, n) for n in top],
    "top_center": [select.face_center(shape, n) for n in top],
    "top_normal": [select.face_normal(shape, n) for n in top],
    "bottom_area": [select.face_area(shape, n) for n in bottom],
    "bottom_center": [select.face_center(shape, n) for n in bottom],
    "bottom_normal": [select.face_normal(shape, n) for n in bottom],
    "plus_x": select.faces_by_normal(shape, 1.0, 0.0, 0.0),
    "tilted": select.faces_by_normal(shape, 0.0, 0.0, 0.7071067811865476),
    "cylinders": select.cylindrical_faces(shape, 5.0),
}))
App.closeDocument(doc.Name)
'''


@pytest.fixture(scope="module")
def selection(tmp_path_factory):
    """Run the selection script inside the CAD and return its result."""
    folder = tmp_path_factory.mktemp("select")
    script = folder / "select_probe.py"
    script.write_text(SCRIPT.replace("REPO_ROOT_PLACEHOLDER", repr(str(REPO_ROOT))),
                      encoding="utf-8")
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    cmd = pack_settings(cfg, "freecad").get("cmd", "")
    assert cmd, "the local configuration has no FreeCAD command"
    proc = subprocess.run([cmd, str(script)], capture_output=True, text=True,
                          timeout=TIMEOUT_S)
    for line in proc.stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX):])
    raise AssertionError("the CAD printed no result:\n" +
                         proc.stdout + proc.stderr)


def test_the_assertion_reports_the_count_it_found():
    """The assertion names the count it expected and the count it found."""
    with pytest.raises(AssertionError) as caught:
        select.assert_count([], 2, "circles of radius 3 mm")

    assert "expected 2 circles of radius 3 mm" in str(caught.value)
    assert "found 0" in str(caught.value)


def test_the_helper_creates_nothing_and_imports_no_core():
    """The helper has no call that creates geometry and no import of the core."""
    tree = ast.parse(HELPER_SOURCE.read_text(encoding="utf-8"))
    banned = {"addObject", "newObject", "removeObject", "addProperty", "removeProperty",
              "makeBox", "makeCylinder", "cut", "fuse", "recompute", "remove"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert getattr(node.func, "attr", "") not in banned
        if isinstance(node, ast.Assign):
            assert not any(isinstance(target, ast.Attribute)
                           for target in node.targets)
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("aturb")
                       for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("aturb")


@pytest.mark.freecad
def test_the_vertical_corner_edges_are_selected(selection):
    """The four vertical corner edges of the demo plate are found."""
    assert selection["edge_count"] == 18
    assert len(selection["corners"]) == 4
    for name in selection["corners"]:
        assert name in selection["vertical"]
    for points in selection["corner_points"]:
        (x0, y0, z0), (x1, y1, z1) = points
        assert abs(x0 - x1) <= 1e-6
        assert abs(y0 - y1) <= 1e-6
        assert abs(z1 - z0) > 1e-6
        assert abs(abs(x0) - 60.0) <= 0.01
        assert abs(abs(y0) - 30.0) <= 0.01


@pytest.mark.freecad
def test_a_circular_edge_is_selected_by_its_radius(selection):
    """The hole circles of the demo plate are found by their radius."""
    assert len(selection["circles"]) == 4
    assert selection["circle_types"] == ["circle"] * 4
    for length in selection["circle_lengths"]:
        assert abs(length / (2.0 * math.pi) - 5.0) <= 0.01


@pytest.mark.freecad
def test_the_assertion_fails_when_the_count_is_not_the_expected_one(selection):
    """The assertion reports the failure when the selected count is wrong."""
    with pytest.raises(AssertionError) as caught:
        select.assert_count(selection["circles"], 2, "circles of radius 3 mm")

    assert "expected 2 circles of radius 3 mm" in str(caught.value)
    assert "found 4" in str(caught.value)


@pytest.mark.freecad
def test_the_radius_assertion_reports_the_edge_and_its_radius(selection):
    """The radius assertion names the edge and the radius it measured."""
    assert "has radius 5.0000 mm" in selection["radius_failure"]
    assert "expected 3.0 mm" in selection["radius_failure"]


@pytest.mark.freecad
def test_the_top_face_is_selected_by_its_normal(selection):
    """The top face of the demo plate is found by its normal and its area."""
    assert selection["face_count"] == 8
    assert len(selection["top"]) == 1
    expected = 120.0 * 60.0 - 2.0 * math.pi * 5.0 ** 2
    for area in selection["top_area"]:
        assert abs(area - expected) <= 0.01
    for center in selection["top_center"]:
        assert abs(center[2] - 5.0) <= 0.01
    for normal in selection["top_normal"]:
        assert normal == [0.0, 0.0, 1.0]


@pytest.mark.freecad
def test_the_bottom_face_is_selected_by_its_normal(selection):
    """The bottom face of the demo plate is found by its normal."""
    assert len(selection["bottom"]) == 1
    expected = 120.0 * 60.0 - 2.0 * math.pi * 5.0 ** 2
    for area in selection["bottom_area"]:
        assert abs(area - expected) <= 0.01
    for center in selection["bottom_center"]:
        assert abs(center[2]) <= 0.01
    for normal in selection["bottom_normal"]:
        assert normal == [0.0, 0.0, -1.0]


@pytest.mark.freecad
def test_a_side_face_and_a_hole_wall_are_selected(selection):
    """A side face is found by its normal and a hole wall by its radius."""
    assert len(selection["plus_x"]) == 1
    assert len(selection["cylinders"]) == 2


@pytest.mark.freecad
def test_the_assertion_fails_when_no_face_matches(selection):
    """The assertion reports the failure when no face matches."""
    with pytest.raises(AssertionError) as caught:
        select.assert_count(selection["tilted"],
                            1, "faces with a tilted normal")

    assert "expected 1 faces with a tilted normal" in str(caught.value)
    assert "found 0" in str(caught.value)
