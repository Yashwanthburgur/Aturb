"""Verify a multi-part assembly from the exported STEP of every part.

The assembly is composed from the exported STEP of each part: every component
is placed on its own copy of the solid of its part, the placed solids are
joined into one compound, and the pairwise interference and the pairwise
clearance are measured with the same neutral modules that judge a single part.

A component is placed with `moved`, which returns a new shape and leaves the
shape it was called on alone, so two components of the same part never share a
shape. Every build123d call used here is recorded in
`docs/api_notes/build123d.md`.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from build123d import Compound, Location, Solid, export_step

from aturb.assembly.manifest import (
    AssemblyComponent,
    AssemblyError,
    AssemblySpec,
    MateExpectation,
)
from aturb.verify.clearance import min_distance
from aturb.verify.interference import interferes, intersection_volume
from aturb.verify.step import StepLoadError, StepModel, load_step

DEFAULT_INTERFERENCE_TOL_MM3 = 1e-3  # starting default
DEFAULT_CLEARANCE_TOL_MM = 0.02  # starting default


@dataclass(frozen=True)
class PairVerification:
    """The verdict for one unordered pair of components.

    The overlap is the material the two components share, in cubic
    millimetres, and the clearance is the smallest gap between them, in
    millimetres. A zero clearance means the two touch or overlap, so the
    overlap says which of the two it is.
    """

    part_a: str
    part_b: str
    intersects: bool
    overlap_volume_mm3: float
    min_clearance_mm: float
    mate_ok: bool
    note: str = ""

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this pair, with no host path."""
        return {
            "part_a": self.part_a,
            "part_b": self.part_b,
            "intersects": self.intersects,
            "overlap_volume_mm3": self.overlap_volume_mm3,
            "min_clearance_mm": self.min_clearance_mm,
            "mate_ok": self.mate_ok,
            "note": self.note,
        }


@dataclass(frozen=True)
class AssemblyReport:
    """The verdict of one assembly.

    The report is deterministic: the same manifest and the same part files
    always give the same numbers. It holds no host path, so it can be written
    to a portable file and sent to a client as it is.
    """

    assembly_id: str
    component_count: int
    all_valid: bool
    has_interference: bool
    all_mates_ok: bool
    total_volume: float
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    bbox_size: tuple[float, float, float]
    pairs: tuple[PairVerification, ...]

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this report, with no host path."""
        return {
            "assembly_id": self.assembly_id,
            "component_count": self.component_count,
            "all_valid": self.all_valid,
            "has_interference": self.has_interference,
            "all_mates_ok": self.all_mates_ok,
            "total_volume": self.total_volume,
            "bbox_min": list(self.bbox_min),
            "bbox_max": list(self.bbox_max),
            "bbox_size": list(self.bbox_size),
            "pairs": [pair.to_dict() for pair in self.pairs],
        }


def compose_assembly_step(
    spec: AssemblySpec,
    part_steps: Mapping[str, Path],
    out_step: Path,
) -> Path:
    """Compose the assembly into one multi-solid STEP file and return its path.

    The file is written through a temporary file in the same folder and then
    moved into place, so a reader never sees a half-written STEP file.
    """
    solids = _placed_solids(spec, part_steps)
    compound = Compound(solids)
    out_step = Path(out_step)
    out_step.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        dir=str(out_step.parent), prefix=out_step.name + ".", suffix=".step")
    temporary = Path(name)
    os.close(handle)
    try:
        written = export_step(compound, str(temporary))
        if written is False or not temporary.is_file() or temporary.stat().st_size == 0:
            raise AssemblyError(
                f"the assembly STEP file {out_step.name} was not written")
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, out_step)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return out_step


def verify_assembly(
    spec: AssemblySpec,
    part_steps: Mapping[str, Path],
    *,
    interference_tol_mm3: float = DEFAULT_INTERFERENCE_TOL_MM3,
    clearance_tol_mm: float = DEFAULT_CLEARANCE_TOL_MM,
) -> AssemblyReport:
    """Verify the assembly and return the report of the whole assembly.

    Every component is placed on its own copy of the solid of its part, every
    unordered pair of components is measured, and every declared mate is
    checked against the pair it names. Raises ``AssemblyError`` when a part of
    the assembly has no STEP file or when its STEP cannot be read.
    """
    solids = _placed_solids(spec, part_steps)
    models = _models(spec, part_steps, solids)
    mates = _mate_index(spec)
    pairs: list[PairVerification] = []
    for first in range(len(spec.components)):
        for second in range(first + 1, len(spec.components)):
            pairs.append(_pair(
                spec.components[first], spec.components[second],
                models[first], models[second], mates,
                interference_tol_mm3, clearance_tol_mm))
    compound = Compound(solids)
    box = compound.bounding_box()
    return AssemblyReport(
        assembly_id=spec.assembly_id,
        component_count=len(spec.components),
        all_valid=all(
            solid.is_valid for solid in solids) and compound.is_valid,
        has_interference=any(pair.intersects for pair in pairs),
        all_mates_ok=all(pair.mate_ok for pair in pairs),
        total_volume=sum(solid.volume for solid in solids),
        bbox_min=(box.min.X, box.min.Y, box.min.Z),
        bbox_max=(box.max.X, box.max.Y, box.max.Z),
        bbox_size=(box.size.X, box.size.Y, box.size.Z),
        pairs=tuple(pairs),
    )


def _placed_solids(spec: AssemblySpec, part_steps: Mapping[str, Path]) -> list[Solid]:
    """Return the placed solid of every component of the assembly."""
    solids: list[Solid] = []
    for component in spec.components:
        step_path = part_steps.get(component.part_id)
        if step_path is None:
            raise AssemblyError(
                f"the assembly has no STEP file for the part "
                f"{component.part_id!r}")
        solids.append(_place_solid(Path(step_path), component))
    return solids


def _place_solid(step_path: Path, component: AssemblyComponent) -> Solid:
    """Return the solid of one component, placed where the manifest says.

    The solid is read from the exported STEP of the part and moved with a copy,
    so the shape that was read is never changed.
    """
    try:
        model = load_step(step_path)
    except StepLoadError as exc:
        raise AssemblyError(
            f"cannot read the STEP of the component {component.name!r}: "
            f"{exc}") from exc
    if len(model.solids) != 1:
        raise AssemblyError(
            f"the STEP of the component {component.name!r} holds "
            f"{len(model.solids)} solids; a component holds exactly one")
    solid = model.solids[0]
    if not solid.is_valid:
        raise AssemblyError(
            f"the solid of the component {component.name!r} is not valid")
    location = Location(component.position, component.rotation_deg)
    return solid.moved(location)


def _models(spec: AssemblySpec, part_steps: Mapping[str, Path],
            solids: list[Solid]) -> list[StepModel]:
    """Return one neutral model per component, holding its placed solid."""
    models: list[StepModel] = []
    for component, solid in zip(spec.components, solids, strict=True):
        path = Path(part_steps[component.part_id])
        models.append(StepModel.from_shape(path, solid))
    return models


def _mate_index(spec: AssemblySpec) -> dict[tuple[str, str], MateExpectation]:
    """Return the mate of every pair of components, keyed by the two names."""
    index: dict[tuple[str, str], MateExpectation] = {}
    for mate in spec.mates:
        key = ((mate.part_a, mate.part_b) if mate.part_a <= mate.part_b
               else (mate.part_b, mate.part_a))
        index.setdefault(key, mate)
    return index


def _pair(first: AssemblyComponent, second: AssemblyComponent,
          first_model: StepModel, second_model: StepModel,
          mates: dict[tuple[str, str], MateExpectation],
          interference_tol_mm3: float, clearance_tol_mm: float) -> PairVerification:
    """Measure one pair of components and judge the mate it declares."""
    overlap = intersection_volume(first_model, second_model)
    intersects = interferes(first_model, second_model, interference_tol_mm3)
    clearance = min_distance(first_model, second_model)
    key = ((first.name, second.name) if first.name <= second.name
           else (second.name, first.name))
    mate_ok, note = _mate_verdict(
        mates.get(key), intersects, clearance, clearance_tol_mm)
    return PairVerification(
        part_a=first.name,
        part_b=second.name,
        intersects=intersects,
        overlap_volume_mm3=overlap,
        min_clearance_mm=clearance,
        mate_ok=mate_ok,
        note=note,
    )


def _mate_verdict(mate: MateExpectation | None, intersects: bool,
                  clearance: float, tolerance: float) -> tuple[bool, str]:
    """Judge one pair against the mate it declares.

    A pair that shares material never passes. A pair with a declared mate
    passes when its clearance lies inside the window of the mate, within the
    tolerance. A pair with no declared mate passes when it shares no material.
    """
    if intersects:
        return False, "the components share material"
    if mate is None:
        return True, ""
    if clearance < mate.min_clearance_mm - tolerance:
        return False, (
            f"the clearance {clearance:.4f} mm is below the expected minimum "
            f"{mate.min_clearance_mm:.4f} mm")
    if (mate.max_clearance_mm is not None
            and clearance > mate.max_clearance_mm + tolerance):
        return False, (
            f"the clearance {clearance:.4f} mm is above the expected maximum "
            f"{mate.max_clearance_mm:.4f} mm")
    return True, ""
