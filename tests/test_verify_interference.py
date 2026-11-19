"""Tests for the intersection and the interference between solids.

Every model is a 10 mm box built with build123d and written to STEP, so the
volumes are measured from exported geometry. Two boxes whose centres are 25 mm
apart leave a 15 mm gap, centres 10 mm apart touch, and centres 5 mm apart
overlap in a 5 x 10 x 10 block of 500 mm^3.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from build123d import Box, Compound, Location, export_step

from aturb.verify.clearance import min_distance
from aturb.verify.interference import (
    Interference,
    find_interferences,
    find_interferences_between,
    interferes,
    intersection_volume,
)
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


def test_separated_solids_share_no_material(tmp_path):
    """Two boxes with a 15 mm gap share nothing."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(25), "second.step")

    assert abs(intersection_volume(first, second)) <= TOL
    assert not interferes(first, second)


def test_touching_solids_share_no_material(tmp_path):
    """Two boxes that share a face have a zero distance but no shared material."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(10), "second.step")

    assert abs(min_distance(first, second)) <= TOL
    assert abs(intersection_volume(first, second)) <= TOL
    assert not interferes(first, second)


def test_overlapping_solids_share_500(tmp_path):
    """Two boxes 5 mm apart overlap in a 5 x 10 x 10 block of 500 mm^3."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(5), "second.step")

    assert abs(intersection_volume(first, second) - 500.0) <= TOL
    assert interferes(first, second)


def test_a_touch_is_told_apart_from_an_overlap(tmp_path):
    """A zero distance hides the difference, the shared volume shows it."""
    first = _model(tmp_path, _box(0), "first.step")
    touching = _model(tmp_path, _box(10), "touching.step")
    overlapping = _model(tmp_path, _box(5), "overlapping.step")

    assert abs(min_distance(first, touching)) <= TOL
    assert abs(min_distance(first, overlapping)) <= TOL
    assert not interferes(first, touching)
    assert interferes(first, overlapping)
    assert abs(intersection_volume(first, touching)) <= TOL
    assert abs(intersection_volume(first, overlapping) - 500.0) <= TOL


def test_one_interfering_pair_in_a_multi_solid_model(tmp_path):
    """Three solids in one STEP file, only the first two overlap."""
    model = _model(tmp_path, Compound(
        [_box(0), _box(5), _box(100)]), "three.step")

    found = find_interferences(model)

    assert len(found) == 1
    assert found[0].first == 0
    assert found[0].second == 1
    assert abs(found[0].volume - 500.0) <= TOL


def test_two_interfering_pairs_in_a_multi_solid_model(tmp_path):
    """Four solids in one STEP file, the first two and the last two overlap."""
    model = _model(
        tmp_path, Compound([_box(0), _box(5), _box(20), _box(25)]), "four.step"
    )

    found = find_interferences(model)

    assert [(item.first, item.second) for item in found] == [(0, 1), (2, 3)]
    for item in found:
        assert abs(item.volume - 500.0) <= TOL


def test_a_multi_solid_model_without_an_overlap_reports_nothing(tmp_path):
    """Two solids far apart in one STEP file do not interfere."""
    model = _model(tmp_path, Compound([_box(0), _box(100)]), "apart.step")

    assert find_interferences(model) == []


def test_touching_solids_in_one_model_are_not_an_interference(tmp_path):
    """Two solids that share a face in one STEP file do not interfere."""
    model = _model(tmp_path, Compound([_box(0), _box(10)]), "touching.step")

    assert find_interferences(model) == []


def test_a_single_solid_model_has_no_pair(tmp_path):
    """A model with one solid has no pair to check."""
    model = _model(tmp_path, _box(0), "one.step")

    assert find_interferences(model) == []


def test_interferences_between_two_models(tmp_path):
    """Every solid of one model is checked against every solid of the other."""
    first = _model(tmp_path, Compound([_box(0), _box(100)]), "first.step")
    second = _model(tmp_path, Compound([_box(5), _box(200)]), "second.step")

    found = find_interferences_between(first, second)

    assert len(found) == 1
    assert found[0].first == 0
    assert found[0].second == 0
    assert abs(found[0].volume - 500.0) <= TOL
    assert interferes(first, second)
    assert abs(intersection_volume(first, second) - 500.0) <= TOL


def test_a_tolerance_above_the_shared_volume_hides_the_interference(tmp_path):
    """A tolerance says how much shared material is enough to interfere."""
    first = _model(tmp_path, _box(0), "first.step")
    second = _model(tmp_path, _box(5), "second.step")

    assert interferes(first, second, 0.0)
    assert not interferes(first, second, 600.0)


def test_an_empty_model_raises(tmp_path):
    """A model without a solid has no intersection and no interference."""
    empty = StepModel.from_shape(tmp_path / "empty.step", Compound([]))
    solid = _model(tmp_path, _box(0), "solid.step")

    with pytest.raises(ValueError):
        intersection_volume(empty, solid)
    with pytest.raises(ValueError):
        interferes(empty, solid)
    with pytest.raises(ValueError):
        find_interferences(empty)


def test_an_interference_is_a_frozen_record():
    """The result of a pair check holds the two positions and the volume."""
    item = Interference(first=0, second=1, volume=500.0)

    assert (item.first, item.second, item.volume) == (0, 1, 500.0)
    with pytest.raises(FrozenInstanceError):
        item.volume = 1.0
