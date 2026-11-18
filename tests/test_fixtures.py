"""Tests for the committed STEP fixture shipped with the stub pack."""

from __future__ import annotations

from pathlib import Path

from build123d import import_step

from tests.fixtures.make_fixtures import FIXTURE_PATH, make_plate_2holes

# Hand calculation of the expected volume:
#
#   Plate volume = 120 x 60 x 5 = 36000 mm^3.
#   Two holes remove 2 x pi x 5^2 x 5 = 785.398 mm^3.
#   Expected volume = 35214.602 mm^3.


def test_plate_fixture(tmp_path):
    """The committed STEP fixture matches a freshly generated one."""
    regenerated = tmp_path / "plate_2holes.step"
    make_plate_2holes(regenerated)

    committed = import_step(str(FIXTURE_PATH))
    fresh = import_step(str(regenerated))

    assert abs(committed.volume - 35214.602) <= 0.01
    assert abs(fresh.volume - 35214.602) <= 0.01


def test_fixture_lives_inside_the_stub_pack():
    """The fixture is a package resource, not a file in the tests folder."""
    assert FIXTURE_PATH == (
        Path(__file__).resolve().parents[1]
        / "packs" / "stub" / "fixtures" / "plate_2holes.step"
    )
    assert FIXTURE_PATH.is_file()
