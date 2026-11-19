"""Tests for the distance and the clearance between two parts.

Every model is a 10 mm box built with build123d and written to STEP, so the
distances are measured from exported geometry. Two boxes whose centres are
25 mm apart leave a 15 mm gap, centres 10 mm apart touch, and centres 5 mm
apart overlap.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from build123d import Box, Compound, Location, export_step

from aturb.verify.clearance import clearance_ok, min_distance
from aturb.verify.step import StepModel, load_step

TOL = 0.01  # starting default


def _box(x: float):
    """A 10 mm box whose centre sits at the given X."""
    return Box(10, 10, 10).locate(Location((x, 0, 0)))


def _model(tmp_path: Path, shape, name: str) -> StepModel:
    """Write a shape to a STEP file and read it back as a model."""
    path = tmp_path / name
    export_step(shape, str(path))
    return load_step(path)


def test_separated_solids_measure_the_gap(tmp_path):
    """Two boxes with a 15 mm gap measure 15.0."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(25), "second.step")

    assert abs(min_distance(first, second) - 15.0) <= TOL


def test_touching_solids_measure_zero(tmp_path):
    """Two boxes that share a face measure 0.0."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(10), "second.step")

    assert abs(min_distance(first, second)) <= TOL


def test_overlapping_solids_measure_zero(tmp_path):
    """Two boxes that overlap measure 0.0."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(5), "second.step")

    assert abs(min_distance(first, second)) <= TOL


def test_clearance_ok_accepts_a_gap_above_the_minimum(tmp_path):
    """A 15 mm gap passes a 10 mm minimum."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(25), "second.step")

    assert clearance_ok(first, second, 10.0)


def test_clearance_ok_rejects_a_gap_below_the_minimum(tmp_path):
    """A 15 mm gap fails a 20 mm minimum."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(25), "second.step")

    assert not clearance_ok(first, second, 20.0)


def test_clearance_ok_accepts_a_gap_equal_to_the_minimum(tmp_path):
    """A gap of exactly the minimum passes."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(25), "second.step")

    assert clearance_ok(first, second, 15.0)


def test_clearance_ok_rejects_touching_solids(tmp_path):
    """Touching solids have no gap, so they fail any positive minimum."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(10), "second.step")

    assert not clearance_ok(first, second, 0.1)


def test_clearance_ok_rejects_overlapping_solids(tmp_path):
    """Overlapping solids have no gap, so they fail any positive minimum."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(5), "second.step")

    assert not clearance_ok(first, second, 0.1)


def test_min_distance_uses_the_closest_pair_of_solids(tmp_path):
    """A model with two solids is measured against its closest solid."""
    pair = Compound([_box(0), _box(100)])
    first = _model(tmp_path, pair, "pair.step")
    second = _model(tmp_path, _box(30), "middle.step")

    assert abs(min_distance(first, second) - 20.0) <= TOL


def test_min_distance_of_an_empty_model_raises(tmp_path):
    """A model without a solid has no distance."""
    empty = StepModel.from_shape(tmp_path / "empty.step", Compound([]))
    solid = _model(tmp_path, _box(0), "solid.step")

    with pytest.raises(ValueError):
        min_distance(empty, solid)
