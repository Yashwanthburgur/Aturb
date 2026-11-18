"""Generate the committed STEP fixture used by the stub pack.

The fixture lives inside the pack (packs/stub/fixtures/) so it is shipped with
the installed package and the stub runner never depends on the tests folder.

Run as a script to write packs/stub/fixtures/plate_2holes.step:

    uv run python tests/fixtures/make_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

from build123d import Box, Cylinder, Location, export_step

PLATE_LENGTH_MM = 120.0
PLATE_WIDTH_MM = 60.0
PLATE_THICKNESS_MM = 5.0
HOLE_DIAMETER_MM = 10.0
HOLE_X_MM = (-40.0, 40.0)
HOLE_Y_MM = 0.0

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "packs" / "stub" / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "plate_2holes.step"


def make_plate_2holes(path: Path) -> None:
    """Build a 120 x 60 x 5 plate with two 10 mm through-holes and export STEP."""
    plate = Box(PLATE_LENGTH_MM, PLATE_WIDTH_MM, PLATE_THICKNESS_MM)
    for x in HOLE_X_MM:
        hole = Cylinder(
            HOLE_DIAMETER_MM / 2, PLATE_THICKNESS_MM
        ).locate(Location((x, HOLE_Y_MM, 0)))
        plate = plate - hole
    export_step(plate, str(path))


def main() -> None:
    """Write every fixture into the stub pack's fixtures folder."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    make_plate_2holes(FIXTURE_PATH)


if __name__ == "__main__":
    main()
