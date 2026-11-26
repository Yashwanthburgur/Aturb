"""Real FreeCAD assembly tests: mating, flush contact and safe coupled edits.

Every part is built by the production runner of the real backend pack, so the
static safety check runs first and every number is measured from the exported
STEP of every part. The offline half of the assembly pipeline lives in
`tests/test_assembly_build.py`.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from build123d import import_step

from aturb.assembly.build import build_assembly
from aturb.assembly.edit import apply_assembly_edit
from aturb.config import load_config
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
CLEARANCE_TOL = 0.02  # starting default
VOLUME_TOL = 0.5  # starting default
BUILD_TIMEOUT_S = 180  # starting default

PLATE = '''"""Mounting plate with a central through-hole.

Units: millimetres. The plate is centred on the origin in X and Y and spans
Z = 0 to PLATE_THICKNESS_MM.
"""

PLATE_LENGTH_MM = 100.0
PLATE_WIDTH_MM = 60.0
PLATE_THICKNESS_MM = 10.0
BORE_DIAMETER_MM = 20.4


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    outline = body.newObject("Sketcher::SketchObject", "OutlineSketch")
    half_x = PLATE_LENGTH_MM / 2
    half_y = PLATE_WIDTH_MM / 2
    corners = [App.Vector(-half_x, -half_y, 0), App.Vector(half_x, -half_y, 0),
               App.Vector(half_x, half_y, 0), App.Vector(-half_x, half_y, 0)]
    for index in range(4):
        outline.addGeometry(
            Part.LineSegment(corners[index], corners[(index + 1) % 4]), False)
    pad = body.newObject("PartDesign::Pad", "PlatePad")
    pad.Profile = outline
    pad.Length = PLATE_THICKNESS_MM
    doc.recompute()

    bore = body.newObject("Sketcher::SketchObject", "BoreSketch")
    bore.Placement = App.Placement(
        App.Vector(0, 0, PLATE_THICKNESS_MM), App.Rotation())
    bore.addGeometry(Part.Circle(
        App.Vector(0, 0, 0), App.Vector(0, 0, 1), BORE_DIAMETER_MM / 2), False)
    hole = body.newObject("PartDesign::Pocket", "CentralBore")
    hole.Profile = bore
    hole.Type = "ThroughAll"
    doc.recompute()

    return body
'''

PIN = '''"""Shoulder pin: a shaft with a wider flange on top of it.

Units: millimetres. The shaft spans Z = 0 to SHAFT_LENGTH_MM and the flange
spans Z = SHAFT_LENGTH_MM to SHAFT_LENGTH_MM + FLANGE_LENGTH_MM.
"""

SHAFT_DIAMETER_MM = 20.0
SHAFT_LENGTH_MM = 15.5
FLANGE_DIAMETER_MM = 36.0
FLANGE_LENGTH_MM = 8.0


def build(doc):
    """Build the part in the given document and return the final object."""
    import FreeCAD as App
    import Part

    body = doc.addObject("PartDesign::Body", "Body")

    profile = body.newObject("Sketcher::SketchObject", "ProfileSketch")
    profile.Placement = App.Placement(
        App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    shaft_r = SHAFT_DIAMETER_MM / 2
    flange_r = FLANGE_DIAMETER_MM / 2
    z1 = SHAFT_LENGTH_MM
    z2 = SHAFT_LENGTH_MM + FLANGE_LENGTH_MM
    points = [App.Vector(0, 0, 0), App.Vector(shaft_r, 0, 0),
              App.Vector(shaft_r, z1, 0), App.Vector(flange_r, z1, 0),
              App.Vector(flange_r, z2, 0), App.Vector(0, z2, 0)]
    for index in range(len(points)):
        profile.addGeometry(
            Part.LineSegment(points[index], points[(index + 1) % len(points)]), False)

    revolution = body.newObject("PartDesign::Revolution", "Revolution")
    revolution.Profile = profile
    revolution.ReferenceAxis = (profile, ["V_Axis"])
    revolution.Angle = 360.0
    doc.recompute()

    return body
'''


def _runner():
    """Return the runner of the real backend pack."""
    if not LOCAL_CONFIG.is_file():
        pytest.skip("the local FreeCAD configuration is not on this machine")
    cfg = load_config(LOCAL_CONFIG)
    return load_runner("freecad", cfg, default_packs_root())


def _plate_source(bore_diameter: float) -> str:
    """Return the source of the mounting plate with the given bore."""
    return PLATE.replace(
        "BORE_DIAMETER_MM = 20.4", f"BORE_DIAMETER_MM = {bore_diameter}")


def _pin_source(shaft_diameter: float, shaft_length: float = 15.5) -> str:
    """Return the source of the shoulder pin with the given shaft."""
    text = PIN.replace(
        "SHAFT_DIAMETER_MM = 20.0", f"SHAFT_DIAMETER_MM = {shaft_diameter}")
    return text.replace(
        "SHAFT_LENGTH_MM = 15.5", f"SHAFT_LENGTH_MM = {shaft_length}")


def _manifest(pin_z: float, minimum: float, maximum: float) -> str:
    """Return the manifest of the plate and the shoulder pin."""
    return f"""
assembly_id = "asm0001"
name = "Plate and shoulder pin"

[[components]]
name = "plate"
part_id = "plt0001"
position = [0.0, 0.0, 0.0]

[[components]]
name = "pin"
part_id = "shf0001"
position = [0.0, 0.0, {pin_z}]

[[mates]]
part_a = "plate"
part_b = "pin"
min_clearance_mm = {minimum}
max_clearance_mm = {maximum}
"""


def _project(tmp_path: Path, pin_source: str, manifest: str) -> Path:
    """Write a project with the two parts and the manifest of the assembly."""
    project = tmp_path / "project"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001.py").write_text(_plate_source(20.4), encoding="utf-8")
    (parts / "shf0001.py").write_text(pin_source, encoding="utf-8")
    assemblies = project / "assemblies"
    assemblies.mkdir(parents=True)
    (assemblies / "asm0001.toml").write_text(manifest, encoding="utf-8")
    return project


def _manifest_path(project: Path) -> Path:
    """Return the manifest of the assembly of a project."""
    return project / "assemblies" / "asm0001.toml"


def _result_path(project: Path) -> Path:
    """Return the result file of the assembly of a project."""
    return project / "out" / "assemblies" / "asm0001" / "assembly_result.toml"


def _step_path(project: Path) -> Path:
    """Return the compound STEP file of the assembly of a project."""
    return project / "out" / "assemblies" / "asm0001" / "asm0001.step"


@pytest.mark.freecad
def test_a_clean_mating_assembly_verifies(tmp_path):
    """A pin in a bore keeps 0.2 mm of radial clearance and 0.5 mm axially."""
    project = _project(
        tmp_path, _pin_source(20.0), _manifest(-5.0, 0.15, 0.25))

    result = build_assembly(
        project, _manifest_path(project), _runner(), timeout_s=BUILD_TIMEOUT_S)

    assert result.status == "ok", result.error
    assert result.report is not None
    assert result.report.component_count == 2
    assert not result.report.has_interference
    assert result.report.all_mates_ok
    pair = result.report.pairs[0]
    assert abs(pair.min_clearance_mm - 0.2) <= CLEARANCE_TOL
    assert pair.overlap_volume_mm3 <= 1e-3
    shape = import_step(str(_step_path(project)))
    assert len(shape.solids()) == 2
    assert abs(shape.volume - result.report.total_volume) <= 0.5


@pytest.mark.freecad
def test_a_flush_seated_shoulder_touches_without_clashing(tmp_path):
    """A flange that sits on the plate touches it and shares no material."""
    project = _project(
        tmp_path, _pin_source(20.0, 15.0), _manifest(-5.0, 0.0, 0.05))

    result = build_assembly(
        project, _manifest_path(project), _runner(), timeout_s=BUILD_TIMEOUT_S)

    assert result.status == "ok", result.error
    assert result.report is not None
    assert not result.report.has_interference
    pair = result.report.pairs[0]
    assert pair.overlap_volume_mm3 <= 1e-3
    assert pair.min_clearance_mm <= 0.01


@pytest.mark.freecad
def test_an_unsafe_edit_is_rejected_and_a_coupled_edit_is_promoted(tmp_path):
    """A clash is refused; the same change with the bore is promoted."""
    project = _project(
        tmp_path, _pin_source(20.0), _manifest(-5.0, 0.15, 0.25))
    runner = _runner()
    first = build_assembly(
        project, _manifest_path(project), runner, timeout_s=BUILD_TIMEOUT_S)
    assert first.status == "ok", first.error
    part = project / "parts" / "shf0001.py"
    before_part = part.read_bytes()
    before_result = _result_path(project).read_bytes()

    unsafe = apply_assembly_edit(
        project, _manifest_path(project), {"shf0001": _pin_source(22.0)},
        runner, timeout_s=BUILD_TIMEOUT_S)

    assert unsafe.status == "failed"
    assert unsafe.promoted is False
    assert unsafe.build.report is not None
    assert unsafe.build.report.has_interference
    overlap = unsafe.build.report.pairs[0].overlap_volume_mm3
    expected = math.pi * (11.0 ** 2 - 10.2 ** 2) * 10.0
    assert abs(overlap - expected) <= VOLUME_TOL
    assert part.read_bytes() == before_part
    assert _result_path(project).read_bytes() == before_result

    coupled = apply_assembly_edit(
        project, _manifest_path(project),
        {"shf0001": _pin_source(22.0), "plt0001": _plate_source(22.4)},
        runner, timeout_s=BUILD_TIMEOUT_S)

    assert coupled.status == "ok", coupled.error
    assert coupled.promoted is True
    assert coupled.build.report is not None
    assert not coupled.build.report.has_interference
    assert coupled.build.report.all_mates_ok
    assert abs(
        coupled.build.report.pairs[0].min_clearance_mm - 0.2) <= CLEARANCE_TOL
    assert "SHAFT_DIAMETER_MM = 22.0" in part.read_text(encoding="utf-8")
