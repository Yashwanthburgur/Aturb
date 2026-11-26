"""Tests for the engineering measurements and the advisory findings.

The committed fixture is the 120 x 60 x 5 plate with two 10 mm through-holes at
X = -40 and X = +40. The other parts are built on the fly with build123d.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from build123d import Box, Cylinder, Location, export_step

from aturb.verify.engineering import (
    DfmFinding,
    DfmThresholds,
    analyze_step,
    check_hole_clearances,
    format_engineering_summary,
)
from aturb.verify.holes import Hole
from aturb.verify.step import StepLoadError

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

TOL = 0.01  # starting default
CENTROID_TOL = 0.001  # starting default


def _write(tmp_path: Path, shape, name: str = "part.step") -> Path:
    """Write a shape to a STEP file and return the path of the file."""
    path = tmp_path / name
    export_step(shape, str(path))
    return path


def _l_shape():
    """Return a solid whose mass centre is not the middle of its box."""
    return Box(20, 10, 10) - Box(10, 5, 5).locate(Location((5, 2.5, 2.5)))


def _stepped_bore():
    """Return a plate with a coaxial counterbore and four bolt holes."""
    part = Box(80, 80, 10)
    part = part - Cylinder(12, 4).locate(Location((0, 0, 3)))
    part = part - Cylinder(7, 12).locate(Location((0, 0, 0)))
    for x, y in ((30, 0), (0, 30), (-30, 0), (0, -30)):
        part = part - Cylinder(3, 12).locate(Location((x, y, 0)))
    return part


def _overlapping_holes():
    """Return a plate whose two holes overlap."""
    part = Box(40, 40, 10)
    part = part - Cylinder(5, 12).locate(Location((4, 0, 0)))
    part = part - Cylinder(5, 12).locate(Location((-4, 0, 0)))
    return part


def test_the_plate_fixture_measures_its_exact_extents():
    """The plate runs from -60 to 60, from -30 to 30 and from -2.5 to 2.5."""
    report = analyze_step(FIXTURE_PATH)

    assert report.bbox_min == pytest.approx((-60.0, -30.0, -2.5), abs=TOL)
    assert report.bbox_max == pytest.approx((60.0, 30.0, 2.5), abs=TOL)
    assert report.bbox_size == pytest.approx((120.0, 60.0, 5.0), abs=TOL)


def test_the_plate_fixture_measures_its_volume_and_its_area():
    """The volume is 35214.602 mm^3 and the area is 16200 mm^2."""
    report = analyze_step(FIXTURE_PATH)

    assert report.volume == pytest.approx(35214.602, abs=TOL)
    assert report.surface_area == pytest.approx(16200.0, abs=TOL)


def test_the_plate_fixture_centre_of_mass_is_the_middle():
    """The plate is symmetric, so its mass centre is the origin."""
    report = analyze_step(FIXTURE_PATH)

    assert report.center_of_mass == pytest.approx(
        (0.0, 0.0, 0.0), abs=CENTROID_TOL)


def test_the_plate_fixture_measures_its_hole_clearances():
    """The holes are 70 mm apart and leave 15 mm to the edge of the plate."""
    report = analyze_step(FIXTURE_PATH)

    assert report.hole_count == 2
    assert report.min_hole_spacing_mm == pytest.approx(70.0, abs=TOL)
    assert report.min_edge_margin_mm == pytest.approx(15.0, abs=TOL)


def test_the_plate_fixture_has_no_findings():
    """A clean part raises no advisory finding."""
    report = analyze_step(FIXTURE_PATH)

    assert report.dfm_findings == ()


def test_the_centre_of_mass_is_the_mass_centre_and_not_the_middle_of_the_box(tmp_path):
    """An asymmetric solid reports its true mass centre, not its box middle."""
    report = analyze_step(_write(tmp_path, _l_shape()))

    expected = (-0.7142857142857143, -
                0.35714285714285715, -0.35714285714285715)
    assert report.center_of_mass == pytest.approx(expected, abs=CENTROID_TOL)
    middle = tuple(
        (low + high) / 2
        for low, high in zip(report.bbox_min, report.bbox_max, strict=True))
    assert middle == pytest.approx((0.0, 0.0, 0.0), abs=CENTROID_TOL)
    assert abs(report.center_of_mass[0] - middle[0]) > 0.1


def test_a_coaxial_stepped_bore_is_not_a_defect(tmp_path):
    """A counterbore and its bore stand on one spot, so they are one feature."""
    report = analyze_step(_write(tmp_path, _stepped_bore()))

    assert report.hole_count == 6
    assert report.min_hole_spacing_mm == pytest.approx(15.0, abs=TOL)
    assert report.min_edge_margin_mm == pytest.approx(7.0, abs=TOL)
    assert report.dfm_findings == ()


def test_the_pure_function_skips_a_coaxial_pair():
    """Two holes on one axis leave no spacing to measure and no finding."""
    holes = [Hole(14.0, 0.0, 0.0, -2.0, True),
             Hole(24.0, 0.0, 0.0, 3.0, False)]

    spacing, margin, findings = check_hole_clearances(
        holes, (-40.0, -40.0, -5.0), (40.0, 40.0, 5.0))

    assert spacing is None
    assert margin == pytest.approx(28.0, abs=TOL)
    assert findings == ()


def test_the_coaxial_tolerance_decides_what_is_one_bore():
    """Two holes within the tolerance are one bore, two holes outside are two."""
    close = [Hole(14.0, 0.0, 0.0, 0.0, True),
             Hole(24.0, 0.04, 0.0, 0.0, False)]
    spacing, _, findings = check_hole_clearances(
        close, (-40.0, -40.0, -5.0), (40.0, 40.0, 5.0))

    assert spacing is None
    assert findings == ()

    apart = [Hole(14.0, 0.0, 0.0, 0.0, True),
             Hole(24.0, 0.06, 0.0, 0.0, False)]
    spacing, _, findings = check_hole_clearances(
        apart, (-40.0, -40.0, -5.0), (40.0, 40.0, 5.0))

    assert spacing == pytest.approx(-18.94, abs=TOL)
    assert [finding.code for finding in findings] == ["DFM1"]


def test_overlapping_holes_are_an_error():
    """Two holes that overlap leave a negative ligament and are an error."""
    holes = [Hole(10.0, -4.0, 0.0, 0.0, True), Hole(10.0, 4.0, 0.0, 0.0, True)]

    spacing, margin, findings = check_hole_clearances(
        holes, (-20.0, -20.0, -5.0), (20.0, 20.0, 5.0))

    assert spacing == pytest.approx(-2.0, abs=TOL)
    assert margin == pytest.approx(11.0, abs=TOL)
    assert [finding.code for finding in findings] == ["DFM1"]
    assert findings[0].severity == "error"


def test_a_thin_ligament_is_a_warning():
    """Two holes that nearly touch leave a thin ligament and are a warning."""
    holes = [Hole(10.0, -5.5, 0.0, 0.0, True), Hole(10.0, 5.5, 0.0, 0.0, True)]

    spacing, _, findings = check_hole_clearances(
        holes, (-20.0, -20.0, -5.0), (20.0, 20.0, 5.0))

    assert spacing == pytest.approx(1.0, abs=TOL)
    assert [finding.code for finding in findings] == ["DFM2"]
    assert findings[0].severity == "warning"


def test_a_ligament_of_exactly_zero_is_a_warning():
    """A ligament of zero is thin, not overlapping."""
    holes = [Hole(10.0, -5.0, 0.0, 0.0, True), Hole(10.0, 5.0, 0.0, 0.0, True)]

    spacing, _, findings = check_hole_clearances(
        holes, (-20.0, -20.0, -5.0), (20.0, 20.0, 5.0))

    assert spacing == pytest.approx(0.0, abs=TOL)
    assert [finding.code for finding in findings] == ["DFM2"]


def test_a_hole_close_to_the_edge_is_a_warning():
    """A hole that nearly reaches the edge of the part is a warning."""
    holes = [Hole(10.0, 44.0, 0.0, 0.0, True)]

    spacing, margin, findings = check_hole_clearances(
        holes, (-50.0, -30.0, -2.5), (50.0, 30.0, 2.5))

    assert spacing is None
    assert margin == pytest.approx(1.0, abs=TOL)
    assert [finding.code for finding in findings] == ["DFM3"]
    assert findings[0].severity == "warning"


def test_a_built_part_with_overlapping_holes_is_an_error(tmp_path):
    """The whole path finds the overlap of a real exported part."""
    report = analyze_step(_write(tmp_path, _overlapping_holes()))

    assert report.min_hole_spacing_mm == pytest.approx(-2.0, abs=TOL)
    assert [finding.code for finding in report.dfm_findings] == ["DFM1"]


def test_a_part_without_holes_has_no_clearances(tmp_path):
    """A part without holes has no spacing, no margin and no finding."""
    report = analyze_step(_write(tmp_path, Box(40, 30, 10)))

    assert report.hole_count == 0
    assert report.min_hole_spacing_mm is None
    assert report.min_edge_margin_mm is None
    assert report.dfm_findings == ()


def test_the_thresholds_can_be_changed():
    """A caller may ask for a thinner ligament than the default."""
    holes = [Hole(10.0, -5.5, 0.0, 0.0, True), Hole(10.0, 5.5, 0.0, 0.0, True)]
    limits = DfmThresholds(min_ligament_mm=0.5, min_edge_margin_mm=0.5)

    spacing, _, findings = check_hole_clearances(
        holes, (-20.0, -20.0, -5.0), (20.0, 20.0, 5.0), limits)

    assert spacing == pytest.approx(1.0, abs=TOL)
    assert findings == ()


def test_the_default_thresholds_are_the_documented_ones():
    """The thresholds of the module are the ones the card names."""
    limits = DfmThresholds()

    assert limits.min_ligament_mm == 2.0
    assert limits.min_edge_margin_mm == 2.0
    assert limits.coaxial_tol_mm == 0.05


def test_a_finding_becomes_a_dict():
    """One finding holds a stable code, a severity and a message."""
    finding = DfmFinding("DFM1", "error", "the holes overlap")

    assert finding.to_dict() == {
        "code": "DFM1", "severity": "error", "message": "the holes overlap"}


def test_the_report_dict_is_json_serializable_and_holds_no_path():
    """The report becomes JSON and never carries a host path."""
    report = analyze_step(FIXTURE_PATH)

    data = report.to_dict()
    text = json.dumps(data)

    assert json.loads(text) == data
    assert str(REPO_ROOT) not in text
    assert "C:" not in text
    assert data == analyze_step(FIXTURE_PATH).to_dict()


def test_the_summary_is_compact_and_holds_no_path():
    """The summary uses the dialect of the repair feedback and no path."""
    report = analyze_step(FIXTURE_PATH)

    text = format_engineering_summary(report)

    assert text.startswith(
        "Engineering geometry (measured from the exported STEP):")
    assert "  volume: 35214.6 mm^3" in text
    assert "  bbox_size: 120.0 x 60.0 x 5.0 mm" in text
    assert "  holes: 2" in text
    assert "  min_hole_spacing: 70.0 mm" in text
    assert "  min_edge_margin: 15.0 mm" in text
    assert str(REPO_ROOT) not in text
    assert "C:" not in text
    assert text == format_engineering_summary(report)


def test_the_summary_lists_the_findings(tmp_path):
    """The summary names every finding with its code and its severity."""
    report = analyze_step(_write(tmp_path, _overlapping_holes()))

    text = format_engineering_summary(report)

    assert "  DFM findings:" in text
    assert "    DFM1 (error):" in text


def test_analyze_step_refuses_a_missing_file(tmp_path):
    """A file that is not there fails the way the loader fails."""
    with pytest.raises(StepLoadError):
        analyze_step(tmp_path / "missing.step")
