"""Tests for the assembly manifest and the assembly verifier.

Every part is a solid built with build123d and written to STEP, so the
assembly is measured from exported geometry and never from a shape in memory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from build123d import Box, Compound, Cylinder, export_step, import_step

from aturb.assembly.manifest import (
    AssemblyComponent,
    AssemblyError,
    AssemblySpec,
    MateExpectation,
    load_assembly,
)
from aturb.verify.assembly import (
    AssemblyReport,
    PairVerification,
    compose_assembly_step,
    verify_assembly,
)

TOL = 0.01  # starting default
VOLUME_TOL = 0.05  # starting default
INTERFERENCE_TOL = 1e-3  # starting default

VALID_MANIFEST = """
assembly_id = "asm0001"
name = "Two plates"

[[components]]
name = "base"
part_id = "plt0001"
position = [0.0, 0.0, 0.0]

[[components]]
name = "top"
part_id = "plt0002"
position = [0.0, 0.0, 6.0]

[[mates]]
part_a = "base"
part_b = "top"
min_clearance_mm = 0.5
max_clearance_mm = 1.5
"""


def _write_step(tmp_path: Path, shape, name: str) -> Path:
    """Write a shape to a STEP file and return the path of the file."""
    path = tmp_path / name
    export_step(shape, str(path))
    return path


def _write_manifest(tmp_path: Path, text: str) -> Path:
    """Write an assembly manifest and return the path of the file."""
    path = tmp_path / "assembly.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _spec(*components: AssemblyComponent,
          mates: tuple[MateExpectation, ...] = ()) -> AssemblySpec:
    """Return an assembly spec built from its components and its mates."""
    return AssemblySpec(
        assembly_id="asm0001", name="Test assembly",
        components=components, mates=mates)


def _plate() -> object:
    """A 40 x 40 x 10 plate with a bore of radius 10.2 through it."""
    return Box(40, 40, 10) - Cylinder(10.2, 20)


def _pin() -> object:
    """A pin of radius 10.0."""
    return Cylinder(10.0, 20)


def test_a_valid_manifest_is_read(tmp_path):
    """A manifest with two components and one mate is read as it is written."""
    spec = load_assembly(_write_manifest(tmp_path, VALID_MANIFEST))

    assert spec.assembly_id == "asm0001"
    assert spec.name == "Two plates"
    assert len(spec.components) == 2
    assert spec.components[0].name == "base"
    assert spec.components[0].part_id == "plt0001"
    assert spec.components[1].position == (0.0, 0.0, 6.0)
    assert spec.components[1].rotation_deg == (0.0, 0.0, 0.0)
    assert len(spec.mates) == 1
    assert spec.mates[0].min_clearance_mm == 0.5
    assert spec.mates[0].max_clearance_mm == 1.5


def test_a_duplicate_component_name_is_refused(tmp_path):
    """Two components may not share a name."""
    text = VALID_MANIFEST.replace('name = "top"', 'name = "base"')

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_a_mate_naming_an_unknown_component_is_refused(tmp_path):
    """A mate may only name components the assembly holds."""
    text = VALID_MANIFEST.replace('part_b = "top"', 'part_b = "ghost"')

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_a_mate_whose_maximum_is_below_its_minimum_is_refused(tmp_path):
    """The clearance window of a mate may not be empty."""
    text = VALID_MANIFEST.replace(
        "max_clearance_mm = 1.5", "max_clearance_mm = 0.1")

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_a_missing_key_is_refused(tmp_path):
    """A manifest that leaves out a key it needs is refused."""
    text = VALID_MANIFEST.replace('name = "Two plates"\n', "")

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_an_unknown_key_is_refused(tmp_path):
    """A manifest that holds a key nobody reads is refused."""
    text = VALID_MANIFEST.replace(
        'name = "Two plates"', 'name = "Two plates"\ncolour = "red"')

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_an_assembly_needs_two_components(tmp_path):
    """One component is not an assembly."""
    text = """
assembly_id = "asm0001"
name = "One plate"

[[components]]
name = "base"
part_id = "plt0001"
"""

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_a_position_that_is_not_three_numbers_is_refused(tmp_path):
    """A position is three finite numbers."""
    text = VALID_MANIFEST.replace(
        "position = [0.0, 0.0, 6.0]", "position = [0.0, 6.0]")

    with pytest.raises(AssemblyError):
        load_assembly(_write_manifest(tmp_path, text))


def test_touching_components_do_not_interfere(tmp_path):
    """Two components that share a face touch but share no material."""
    first = _write_step(tmp_path, Box(10, 10, 10), "first.step")
    second = _write_step(tmp_path, Box(10, 10, 10), "second.step")
    spec = _spec(
        AssemblyComponent(name="base", part_id="p1"),
        AssemblyComponent(name="top", part_id="p2", position=(10.0, 0.0, 0.0)),
        mates=(MateExpectation(part_a="base", part_b="top",
                               min_clearance_mm=0.0, max_clearance_mm=0.05),))

    report = verify_assembly(spec, {"p1": first, "p2": second})

    assert not report.has_interference
    assert report.pairs[0].overlap_volume_mm3 <= INTERFERENCE_TOL
    assert abs(report.pairs[0].min_clearance_mm) <= TOL
    assert report.pairs[0].mate_ok
    assert report.all_mates_ok


def test_a_pin_in_a_bore_keeps_its_radial_clearance(tmp_path):
    """A pin of radius 10.0 in a bore of radius 10.2 leaves 0.2 mm."""
    plate = _write_step(tmp_path, _plate(), "plate.step")
    pin = _write_step(tmp_path, _pin(), "pin.step")
    spec = _spec(
        AssemblyComponent(name="plate", part_id="plt0001"),
        AssemblyComponent(name="pin", part_id="shf0001"),
        mates=(MateExpectation(part_a="plate", part_b="pin",
                               min_clearance_mm=0.15, max_clearance_mm=0.25),))

    report = verify_assembly(spec, {"plt0001": plate, "shf0001": pin})

    assert not report.has_interference
    assert abs(report.pairs[0].min_clearance_mm - 0.2) <= TOL
    assert report.pairs[0].mate_ok
    assert report.all_mates_ok


def test_a_mate_that_asks_for_more_clearance_than_there_is_fails(tmp_path):
    """A mate whose window the clearance misses is not satisfied."""
    plate = _write_step(tmp_path, _plate(), "plate.step")
    pin = _write_step(tmp_path, _pin(), "pin.step")
    spec = _spec(
        AssemblyComponent(name="plate", part_id="plt0001"),
        AssemblyComponent(name="pin", part_id="shf0001"),
        mates=(MateExpectation(part_a="plate", part_b="pin",
                               min_clearance_mm=0.3, max_clearance_mm=0.5),))

    report = verify_assembly(spec, {"plt0001": plate, "shf0001": pin})

    assert not report.has_interference
    assert not report.pairs[0].mate_ok
    assert not report.all_mates_ok
    assert report.pairs[0].note


def test_components_that_overlap_interfere(tmp_path):
    """Two boxes that overlap share 500 mm^3 of material."""
    first = _write_step(tmp_path, Box(10, 10, 10), "first.step")
    second = _write_step(tmp_path, Box(10, 10, 10), "second.step")
    spec = _spec(
        AssemblyComponent(name="base", part_id="p1"),
        AssemblyComponent(name="top", part_id="p2", position=(5.0, 0.0, 0.0)),
        mates=(MateExpectation(part_a="base", part_b="top"),))

    report = verify_assembly(spec, {"p1": first, "p2": second})

    assert report.has_interference
    assert abs(report.pairs[0].overlap_volume_mm3 - 500.0) <= VOLUME_TOL
    assert not report.pairs[0].mate_ok
    assert not report.all_mates_ok


def test_a_part_without_a_step_file_is_refused(tmp_path):
    """An assembly whose part has no STEP file cannot be verified."""
    first = _write_step(tmp_path, Box(10, 10, 10), "first.step")
    spec = _spec(
        AssemblyComponent(name="base", part_id="p1"),
        AssemblyComponent(name="top", part_id="p2"))

    with pytest.raises(AssemblyError):
        verify_assembly(spec, {"p1": first})


def test_the_composed_step_reloads_as_a_multi_solid_compound(tmp_path):
    """The composed file holds both solids and the volume of the assembly."""
    first = _write_step(tmp_path, Box(10, 10, 10), "first.step")
    second = _write_step(tmp_path, Box(10, 10, 10), "second.step")
    spec = _spec(
        AssemblyComponent(name="base", part_id="p1"),
        AssemblyComponent(name="top", part_id="p2", position=(30.0, 0.0, 0.0)))
    out_step = tmp_path / "out" / "asm0001.step"

    compose_assembly_step(spec, {"p1": first, "p2": second}, out_step)

    assert out_step.is_file()
    shape = import_step(str(out_step))
    assert isinstance(shape, Compound)
    assert len(shape.solids()) == 2
    report = verify_assembly(spec, {"p1": first, "p2": second})
    assert abs(shape.volume - report.total_volume) <= VOLUME_TOL
    assert report.component_count == 2
    assert report.all_valid


def test_the_report_is_json_safe_and_holds_no_host_path(tmp_path):
    """The report can be sent to a client as it is."""
    first = _write_step(tmp_path, Box(10, 10, 10), "first.step")
    second = _write_step(tmp_path, Box(10, 10, 10), "second.step")
    spec = _spec(
        AssemblyComponent(name="base", part_id="p1"),
        AssemblyComponent(name="top", part_id="p2", position=(30.0, 0.0, 0.0)))

    report = verify_assembly(spec, {"p1": first, "p2": second})
    payload = report.to_dict()
    text = json.dumps(payload)

    assert isinstance(report, AssemblyReport)
    assert isinstance(report.pairs[0], PairVerification)
    assert payload["component_count"] == 2
    assert len(payload["pairs"]) == 1
    assert str(tmp_path) not in text
    assert ":\\" not in text
