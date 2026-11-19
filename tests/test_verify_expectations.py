"""Tests for the expected values of the demo project.

The committed expectation file holds the hand calculation of the demo plate:
120 x 60 x 5 = 36000 mm^3, minus 2 x pi x 5^2 x 5 = 785.398 mm^3, so
35214.602 mm^3, with two 10 mm holes 80 mm apart. The committed fixture is
the same plate, so it must satisfy every expectation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.verify.expectations import checks_from_expectations, load_expectations
from aturb.verify.step import load_step

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECT_PATH = REPO_ROOT / "projects" / "demo" / "expect" / "plt0001.toml"
FIXTURE_PATH = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"

TOL = 0.01  # starting default


def _write(tmp_path: Path, text: str) -> Path:
    """Write an expectation file and return its path."""
    path = tmp_path / "expect.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _numbers_only(value) -> bool:
    """True when a value holds numbers and lists of numbers only."""
    if isinstance(value, list):
        return all(_numbers_only(item) for item in value)
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def test_the_demo_expectations_load():
    """The committed expectation file loads into a table of values."""
    expected = load_expectations(EXPECT_PATH)

    assert isinstance(expected, dict)
    assert set(expected) == {
        "volume",
        "bbox",
        "hole_count",
        "hole_diameter",
        "hole_positions",
    }


def test_the_demo_expectations_hold_the_hand_values():
    """The values are the hand calculation, with the types the file holds."""
    expected = load_expectations(EXPECT_PATH)

    assert expected["volume"] == 35214.602
    assert isinstance(expected["volume"], float)
    assert expected["bbox"] == [120.0, 60.0, 5.0]
    assert expected["hole_count"] == 2
    assert isinstance(expected["hole_count"], int)
    assert expected["hole_diameter"] == 10.0
    assert expected["hole_positions"] == [[-40.0, 0.0], [40.0, 0.0]]


def test_the_demo_expectations_hold_numbers_only():
    """The file holds numbers and lists of numbers, nothing else."""
    expected = load_expectations(EXPECT_PATH)

    for value in expected.values():
        assert _numbers_only(value)


def test_the_fixture_satisfies_the_demo_expectations():
    """Every expected value of the demo plate is met by the fixture."""
    model = load_step(FIXTURE_PATH)
    expected = load_expectations(EXPECT_PATH)

    results = checks_from_expectations(model, expected)

    assert results
    failed = [result for result in results if not result.passed]
    assert failed == [], [result.to_dict() for result in failed]


def test_every_expected_value_gives_a_result():
    """The volume, the box, the count, the diameters and the positions."""
    model = load_step(FIXTURE_PATH)
    expected = load_expectations(EXPECT_PATH)

    results = checks_from_expectations(model, expected)

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


def test_a_wrong_expected_volume_produces_one_failing_result():
    """A wrong expected volume fails one result and leaves the rest passing."""
    model = load_step(FIXTURE_PATH)
    expected = load_expectations(EXPECT_PATH)
    wrong = {**expected, "volume": 1.0}

    results = checks_from_expectations(model, wrong)

    failed = [result for result in results if not result.passed]
    assert len(failed) == 1
    assert failed[0].name == "volume"
    assert failed[0].expected == 1.0
    assert failed[0].actual == pytest.approx(35214.602, abs=TOL)


def test_a_wrong_expected_hole_position_produces_one_failing_result():
    """A wrong expected hole position fails one result."""
    model = load_step(FIXTURE_PATH)
    expected = load_expectations(EXPECT_PATH)
    wrong = {**expected, "hole_positions": [[-30.0, 0.0], [40.0, 0.0]]}

    results = checks_from_expectations(model, wrong)

    failed = [result for result in results if not result.passed]
    assert len(failed) == 1
    assert failed[0].name == "hole_0_x"
    assert failed[0].expected == -30.0
    assert failed[0].actual == pytest.approx(-40.0, abs=TOL)


def test_a_wrong_expected_hole_count_fails_the_count():
    """A wrong expected hole count fails the count result."""
    model = load_step(FIXTURE_PATH)
    expected = load_expectations(EXPECT_PATH)
    wrong = {
        **expected,
        "hole_count": 3,
        "hole_positions": [[-40.0, 0.0], [0.0, 0.0], [40.0, 0.0]],
    }

    results = checks_from_expectations(model, wrong)

    count = [result for result in results if result.name == "hole_count"]
    assert len(count) == 1
    assert not count[0].passed
    assert count[0].expected == 3.0
    assert count[0].actual == 2.0


def test_a_missing_expectation_file_raises(tmp_path):
    """A file that is not there cannot be loaded."""
    with pytest.raises(FileNotFoundError):
        load_expectations(tmp_path / "absent.toml")


def test_malformed_toml_raises(tmp_path):
    """A file that is not valid TOML is refused."""
    path = _write(tmp_path, "volume = = 1.0")

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_missing_required_value_raises(tmp_path):
    """A file without every expected value is refused."""
    path = _write(tmp_path, "volume = 35214.602\n")

    with pytest.raises(ValueError):
        load_expectations(path)


def test_an_unknown_value_raises(tmp_path):
    """A file with a value the schema does not know is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n"
        "feature_tree = 'sketch'\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_value_that_is_not_a_number_raises(tmp_path):
    """A file with a value that is not a number is refused."""
    path = _write(
        tmp_path,
        "volume = '35214.602'\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_boolean_value_raises(tmp_path):
    """A file with a boolean where a number belongs is refused."""
    path = _write(
        tmp_path,
        "volume = true\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_negative_value_raises(tmp_path):
    """A file with a negative measurement is refused."""
    path = _write(
        tmp_path,
        "volume = -1.0\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_bounding_box_of_the_wrong_size_raises(tmp_path):
    """A bounding box that is not three numbers is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_position_that_is_not_a_pair_raises(tmp_path):
    """A hole position that is not x and y is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0, 0.0], [40.0, 0.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_count_that_disagrees_with_the_positions_raises(tmp_path):
    """A hole count that does not match the positions is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 3\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)


def test_a_hole_count_that_is_not_a_whole_number_raises(tmp_path):
    """A hole count that is not a whole number is refused."""
    path = _write(
        tmp_path,
        "volume = 35214.602\n"
        "bbox = [120.0, 60.0, 5.0]\n"
        "hole_count = 2.5\n"
        "hole_diameter = 10.0\n"
        "hole_positions = [[-40.0, 0.0], [40.0, 0.0]]\n",
    )

    with pytest.raises(ValueError):
        load_expectations(path)
