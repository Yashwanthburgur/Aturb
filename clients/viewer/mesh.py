"""Turn an exported STEP file into a JSON mesh.

The viewer draws triangles, so the exported STEP has to become vertices and
triangle indices. The core reads the STEP with its neutral reader and the
tessellation uses the verified build123d call recorded in
`docs/api_notes/build123d.md`:

    vertices, triangles = model.shape.tessellate(tolerance, angular_tolerance)

The payload is plain JSON: flat positions, flat zero-based triangle indices
and the two counts. The browser derives the normals and the bounding box from
it, so nothing else has to travel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aturb.verify.step import StepLoadError, load_step

DEFAULT_TOLERANCE_MM = 0.1  # starting default
DEFAULT_ANGULAR_TOLERANCE_RAD = 0.1  # starting default


class MeshError(ValueError):
    """Raised when a STEP file cannot be turned into a mesh."""


@dataclass(frozen=True)
class MeshPayload:
    """One mesh: flat positions, flat triangle indices and the two counts.

    The positions are flat, three numbers per vertex, and the indices are
    flat, three zero-based indices per triangle.
    """

    positions: tuple[float, ...]
    indices: tuple[int, ...]
    vertex_count: int
    triangle_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready form of the payload."""
        return {
            "positions": list(self.positions),
            "indices": list(self.indices),
            "vertex_count": self.vertex_count,
            "triangle_count": self.triangle_count,
        }


def tessellate_step(
    step_path: Path,
    tolerance: float = DEFAULT_TOLERANCE_MM,
    angular_tolerance: float = DEFAULT_ANGULAR_TOLERANCE_RAD,
) -> MeshPayload:
    """Read a STEP file and tessellate it into a mesh payload.

    Raises ``MeshError`` when a tolerance is not positive, when the file
    cannot be read, when the tessellation is empty, and when the result is not
    a valid triangle mesh.
    """
    if tolerance <= 0:
        raise MeshError(f"the tolerance must be positive, got {tolerance}")
    if angular_tolerance <= 0:
        raise MeshError(
            f"the angular tolerance must be positive, got {angular_tolerance}")
    try:
        model = load_step(step_path)
    except StepLoadError as exc:
        raise MeshError(str(exc)) from exc
    try:
        vertices, triangles = model.shape.tessellate(
            tolerance, angular_tolerance)
    except Exception as exc:
        raise MeshError(
            f"the STEP file {step_path} cannot be tessellated: {exc}") from exc
    if not vertices:
        raise MeshError(
            f"the STEP file {step_path} tessellated into no vertex")
    if not triangles:
        raise MeshError(
            f"the STEP file {step_path} tessellated into no triangle")
    return MeshPayload(
        positions=_positions(vertices),
        indices=_indices(triangles, len(vertices)),
        vertex_count=len(vertices),
        triangle_count=len(triangles),
    )


def _positions(vertices) -> tuple[float, ...]:
    """Return the flat coordinates of the vertices, checked for finiteness."""
    flat: list[float] = []
    for vertex in vertices:
        for value in (vertex.X, vertex.Y, vertex.Z):
            number = float(value)
            if not math.isfinite(number):
                raise MeshError(
                    "the tessellation holds a non-finite coordinate")
            flat.append(number)
    return tuple(flat)


def _indices(triangles, vertex_count: int) -> tuple[int, ...]:
    """Return the flat triangle indices, checked against the vertex count."""
    flat: list[int] = []
    for triangle in triangles:
        if len(triangle) != 3:
            raise MeshError(
                "the tessellation holds a triangle that is not a triangle")
        for value in triangle:
            index = int(value)
            if index < 0 or index >= vertex_count:
                raise MeshError(
                    f"the tessellation holds an index outside the vertices: {index}")
            flat.append(index)
    return tuple(flat)
