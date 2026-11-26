"""Tests for the optional per-hole diameters of an expectation file.

An expectation file may name the diameter of every hole, so a bore and its
counterbore are each measured against their own diameter. The model used here
is a 40 x 40 x 20 block with a 14 mm bore through it and a 24 mm counterbore
from the top: the two holes share one place and are told apart by their
diameter alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from build123d import Box, Cylinder, Location, export_step

from aturb.verify.expectations import checks_from_expectations, load_expectations
from aturb.verify.step import load_step

TOL = 0.01  # starting default

# Hand volume: 32000 - pi x 7^2 x 20 - (pi x 12^2 x 8 - pi x 7^2 x 8)
# = 26533.628782753596 mm^3.
STEPPED_VOLUME = 26533.628782753596


def _write(tmp_path: Path, text: str) -> Path:
    """Write an expectation file and return its path."""
    path = tmp_path / "expect.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _stepped_bore(tmp_path: Path):
    """Return a model with a 14 mm bore and its 24 mm counterbore."""
    part = (
        Box(40, 40, 20)
        - Cylinder(7, 20)
        - Cylinder(12, 8).locate(Location((0, 0, 6)))
    )
    path = tmp_path / "stepped.step"
    export_step(part, str(path))
    return load_step(path)


def _stepped_expectations(**overrides) -> dict:
    """Return the expected values of the stepped bore."""
    expected = {
        "volume": STEPPED_VOLUME,
        "bbox": [40.0, 40.0, 20.0],
        "hole_count": 2,
        "hole_diameter": 14.0,
        "hole_positions": [[0.0, 0.0], [0.0, 0.0]],
    }
    expected.update(overrides)
    return expected


def test_a_file_without_per_hole_diameters_holds_the_five_values(tmp_path):
    """A file that names no per-hole diameter holds exactly the five values."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    expected = load_expectations(path)

    assert set(expected) == {
        "volume",
        "bbox",
        "hole_count",
        "hole_diameter",
        "hole_positions",
    }


def test_the_per_hole_diameters_are_optional(tmp_path):
    """A file may name the diameter of every hole."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n"
        "hole_diameters = [10.0, 12.0]\n",
    )

    expected = load_expectations(path)

    assert expected["hole_diameters"] == [10.0, 12.0]


def test_per_hole_diameters_that_disagree_with_the_positions_raise(tmp_path):
    """A list of diameters of the wrong length is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n"
        "hole_diameters = [10.0]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


@pytest.mark.parametrize("diameter", ["0.0", "-6.0"])
def test_a_per_hole_diameter_that_is_not_positive_raises(tmp_path, diameter):
    """A diameter of zero or less is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 1\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0]]\n"
        f"hole_diameters = [{diameter}]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_per_hole_diameter_that_is_not_a_number_raises(tmp_path):
    """A diameter that is not a number is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 1\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0]]\n"
        "hole_diameters = [\"wide\"]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_the_scalar_hole_diameter_still_names_every_hole(tmp_path):
    """Without per-hole diameters every hole is measured against the one value."""
    model = _stepped_bore(tmp_path)

    results = checks_from_expectations(model, _stepped_expectations())

    diameters = [
        result for result in results if result.name.endswith("_diameter")]
    assert [result.name for result in diameters] == [
        "hole_0_diameter",
        "hole_1_diameter",
    ]
    assert diameters[0].passed
    assert not diameters[1].passed
    assert diameters[1].expected == 14.0
    assert diameters[1].actual == pytest.approx(24.0, abs=TOL)


def test_the_per_hole_diameters_pair_a_coaxial_stepped_bore(tmp_path):
    """A bore and its counterbore are each measured against their own diameter."""
    model = _stepped_bore(tmp_path)
    expected = _stepped_expectations(hole_diameters=[14.0, 24.0])

    results = checks_from_expectations(model, expected)

    failed = [result for result in results if not result.passed]
    assert failed == [], [result.to_dict() for result in failed]
    assert [result.name for result in results] == [
        "volume",
        "bbox_x",
        "bbox_y",
        "bbox_z",
        "hole_count",
        "hole_0_diameter",
        "hole_1_diameter",
        "hole_0_x",
        "hole_0_y",
        "hole_1_x",
        "hole_1_y",
    ]


def test_a_wrong_per_hole_diameter_fails_the_exact_check(tmp_path):
    """A wrong diameter for one hole fails only that hole's diameter check."""
    model = _stepped_bore(tmp_path)
    expected = _stepped_expectations(hole_diameters=[15.0, 24.0])

    results = checks_from_expectations(model, expected)

    failed = [result for result in results if not result.passed]
    assert len(failed) == 1
    assert failed[0].name == "hole_0_diameter"
    assert failed[0].expected == 15.0
    assert failed[0].actual == pytest.approx(14.0, abs=TOL)


def test_the_per_hole_diameters_do_not_change_the_order_of_the_checks(tmp_path):
    """The order of the checks is the same with and without the diameters."""
    model = _stepped_bore(tmp_path)

    without = checks_from_expectations(model, _stepped_expectations())
    with_diameters = checks_from_expectations(
        model, _stepped_expectations(hole_diameters=[14.0, 24.0]))

    assert [result.name for result in without] == [
        result.name for result in with_diameters]
