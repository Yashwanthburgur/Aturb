"""Read an exported STEP file into neutral geometry.

The core judges geometry with build123d, never with a CAD. Every call used
here is recorded in docs/api_notes/build123d.md.

Two facts from that register shape this module:

- ``import_step`` returns a ``Solid`` for a file with one solid and a
  ``Compound`` for a file with several, so the model always normalises the
  imported shape through ``shape.solids()``.
- ``import_step`` does not raise for a file that is not a STEP. It returns an
  empty shape and the reader writes a parse error to stderr, so a file with no
  solid is treated as unreadable here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from build123d import Edge, Face, Shape, Solid, Vector, import_step


class StepLoadError(Exception):
    """Raised when a STEP file cannot be read as a usable model."""


@dataclass(frozen=True)
class StepModel:
    """One STEP file read into neutral geometry.

    The imported shape is kept for aggregate measurements, and the solids are
    normalised so a one-solid file and a many-solid file are handled the same
    way. ``is_single_solid`` says which of the two a file is.
    """

    path: Path
    shape: Shape
    solids: tuple[Solid, ...]

    @classmethod
    def from_shape(cls, path: Path, shape: Shape) -> "StepModel":
        """Build a model from an imported shape, normalising its solids."""
        return cls(path=path, shape=shape, solids=tuple(shape.solids()))

    @property
    def is_single_solid(self) -> bool:
        """True when the file holds exactly one solid.

        A STEP file may hold several solids, so this says plainly whether the
        model is one part or several.
        """
        return len(self.solids) == 1

    @property
    def faces(self) -> tuple[Face, ...]:
        """Every face of every solid in the model."""
        return tuple(face for solid in self.solids for face in solid.faces())

    @property
    def edges(self) -> tuple[Edge, ...]:
        """Every edge of every solid in the model."""
        return tuple(edge for solid in self.solids for edge in solid.edges())

    @property
    def volume(self) -> float:
        """Total volume of the solids in the model."""
        return sum(solid.volume for solid in self.solids)

    @property
    def area(self) -> float:
        """Total surface area of the solids in the model."""
        return sum(solid.area for solid in self.solids)

    @property
    def is_valid(self) -> bool:
        """True when the model holds solids and every one of them is valid."""
        return bool(self.solids) and all(solid.is_valid for solid in self.solids)

    @property
    def bbox_size(self) -> Vector:
        """Size of the bounding box of the whole model.

        This is an aggregate measurement, so it is taken from the imported
        shape rather than from one solid.
        """
        return self.shape.bounding_box().size


def load_step(path: Path | str) -> StepModel:
    """Read a STEP file into a neutral model.

    Raises ``StepLoadError`` when the file is missing, cannot be read, or
    holds no readable solid.
    """
    path = Path(path)
    if not path.is_file():
        raise StepLoadError(f"no STEP file at {path}")
    try:
        shape = import_step(str(path))
    except FileNotFoundError as exc:
        raise StepLoadError(f"no STEP file at {path}") from exc
    except Exception as exc:
        raise StepLoadError(
            f"cannot read the STEP file {path}: {exc}") from exc
    model = StepModel.from_shape(path, shape)
    if not model.solids:
        raise StepLoadError(f"the STEP file {path} holds no readable solid")
    return model
