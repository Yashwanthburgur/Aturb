"""Spike: verify the build123d calls Phase 3 needs for neutral STEP checks.

Run from the repository root:

    uv run python tools/spikes/b3d_inspect.py

Every line printed here is the evidence for a row in docs/api_notes/build123d.md.
Only calls that this script actually runs may be recorded there.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from build123d import (
    Box,
    CenterOf,
    Compound,
    GeomType,
    Location,
    export_step,
    import_step,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"


def show(label: str, value: object) -> None:
    """Print one labelled fact."""
    print(f"{label}: {value}")


def inspect_fixture() -> None:
    """Inspect the committed plate-with-two-holes fixture."""
    print("== fixture ==")
    shape = import_step(str(FIXTURE))
    show("type", type(shape).__name__)
    show("solids", len(shape.solids()))
    show("faces", len(shape.faces()))
    show("edges", len(shape.edges()))
    show("volume", shape.volume)
    show("area", shape.area)
    show("is_valid", shape.is_valid)
    show("bbox", shape.bounding_box().size)

    kinds: dict[str, int] = {}
    for face in shape.faces():
        key = str(face.geom_type)
        kinds[key] = kinds.get(key, 0) + 1
    show("face_types", kinds)

    print("== cylindrical faces ==")
    for face in shape.faces():
        if face.geom_type != GeomType.CYLINDER:
            continue
        circles = [e for e in face.edges() if e.geom_type == GeomType.CIRCLE]
        show("radius", face.radius)
        show("center_default", face.center())
        show("center_mass", face.center(CenterOf.MASS))
        show("axis_position", face.axis_of_rotation.position)
        show("axis_direction", face.axis_of_rotation.direction)
        show("circular_edges", len(circles))
        show("face_area", face.area)

    print("== circular edges ==")
    for edge in shape.edges():
        if edge.geom_type != GeomType.CIRCLE:
            continue
        show("radius", edge.radius)
        show("arc_center", edge.arc_center)
        show("center_default", edge.center())
        show("length", edge.length)


def inspect_distances() -> None:
    """Measure the gap and the overlap between two boxes."""
    print("== distance and intersection ==")
    first = Box(10, 10, 10)
    apart = Box(10, 10, 10).locate(Location((25, 0, 0)))
    overlap = Box(10, 10, 10).locate(Location((5, 0, 0)))
    show("gap_distance", first.distance_to(apart))
    show("overlap_distance", first.distance_to(overlap))
    show("closest_points", first.closest_points(apart))
    show("distance_with_points", first.distance_to_with_closest_points(apart))
    show("overlap_and_volume", (first & overlap).volume)
    show("overlap_and_solids", len((first & overlap).solids()))
    show("apart_and_volume", (first & apart).volume)
    show("apart_and_solids", len((first & apart).solids()))
    listed = first.intersect(overlap)
    show("intersect_type", type(listed).__name__)
    show("intersect_len", len(listed))
    show("intersect_item_volume", listed[0].volume)
    show("intersect_disjoint", first.intersect(apart))


def inspect_multi_solid() -> None:
    """Export two solids into one STEP file and import it back."""
    print("== multi-solid STEP ==")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "two_solids.step"
        compound = Compound([
            Box(10, 10, 10),
            Box(10, 10, 10).locate(Location((30, 0, 0))),
        ])
        export_step(compound, str(path))
        shape = import_step(str(path))
        show("type", type(shape).__name__)
        show("solids", len(shape.solids()))
        show("solid_volumes", [round(solid.volume, 4)
             for solid in shape.solids()])
        show("volume", shape.volume)
        show("faces", len(shape.faces()))


def main() -> None:
    """Run every check and print the evidence."""
    inspect_fixture()
    inspect_distances()
    inspect_multi_solid()


if __name__ == "__main__":
    main()
