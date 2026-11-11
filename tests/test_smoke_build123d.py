"""Permanent build123d smoke test: a cube must survive a STEP round trip unchanged.

Uses only calls recorded in docs/api_notes/build123d.md.
"""

from build123d import Box, export_step, import_step


def test_cube_step_round_trip(tmp_path):
    box = Box(10, 10, 10)  # starting default

    step_path = tmp_path / "box.step"
    assert export_step(box, step_path)
    assert step_path.exists()

    shape = import_step(step_path)

    assert abs(shape.volume - 1000) <= 1e-6

    size = shape.bounding_box().size
    assert abs(size.X - 10) <= 1e-6
    assert abs(size.Y - 10) <= 1e-6
    assert abs(size.Z - 10) <= 1e-6

    assert shape.is_valid
