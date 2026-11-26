"""Engineering measurements and advisory findings from an exported STEP file.

The module measures the facts an engineer asks about a part: the extents of
its bounding box, its volume, its surface area, its centre of mass, the
smallest ligament between two holes and the smallest wall between a hole and
the edge of the part. The findings are advisories, not verdicts: they never
raise, never block and never change the result of a check.

Two holes whose axes stand on the same spot are one stepped bore and not two
holes, so a pair whose centres coincide within the coaxial tolerance is left
out of the ligament measurement. A stepped bore is not a defect.
Every build123d call it uses is recorded in docs/api_notes/build123d.md.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from build123d import CenterOf

from aturb.verify.holes import Hole, find_holes
from aturb.verify.step import StepModel, load_step

MIN_LIGAMENT_MM = 2.0  # starting default
MIN_EDGE_MARGIN_MM = 2.0  # starting default
COAXIAL_TOL_MM = 0.05  # starting default

DFM1 = "DFM1"
DFM2 = "DFM2"
DFM3 = "DFM3"

ENGINEERING_HEADER = "Engineering geometry (measured from the exported STEP):"
INDENT = "  "


@dataclass(frozen=True)
class DfmThresholds:
    """The advisory thresholds of the manufacturability findings."""

    min_ligament_mm: float = MIN_LIGAMENT_MM  # starting default
    min_edge_margin_mm: float = MIN_EDGE_MARGIN_MM  # starting default
    coaxial_tol_mm: float = COAXIAL_TOL_MM  # starting default


@dataclass(frozen=True)
class DfmFinding:
    """One advisory finding: a stable code, a severity and a readable message."""

    code: str
    severity: str
    message: str

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this finding."""
        return {"code": self.code, "severity": self.severity,
                "message": self.message}


@dataclass(frozen=True)
class EngineeringReport:
    """The engineering facts of one exported STEP file.

    The two clearances are ``None`` when they cannot be measured.
    """

    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    bbox_size: tuple[float, float, float]
    volume: float
    surface_area: float
    center_of_mass: tuple[float, float, float]
    hole_count: int
    min_hole_spacing_mm: float | None
    min_edge_margin_mm: float | None
    dfm_findings: tuple[DfmFinding, ...]

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this report, with no host path."""
        return {
            "bbox_min": list(self.bbox_min),
            "bbox_max": list(self.bbox_max),
            "bbox_size": list(self.bbox_size),
            "volume": self.volume,
            "surface_area": self.surface_area,
            "center_of_mass": list(self.center_of_mass),
            "hole_count": self.hole_count,
            "min_hole_spacing_mm": self.min_hole_spacing_mm,
            "min_edge_margin_mm": self.min_edge_margin_mm,
            "dfm_findings": [finding.to_dict() for finding in self.dfm_findings],
        }


def analyze_step(path: Path, thresholds: DfmThresholds | None = None) -> EngineeringReport:
    """Measure the engineering facts of one exported STEP file."""
    model = load_step(path)
    box = model.shape.bounding_box()
    bbox_min = (box.min.X, box.min.Y, box.min.Z)
    bbox_max = (box.max.X, box.max.Y, box.max.Z)
    bbox_size = (box.size.X, box.size.Y, box.size.Z)
    holes = find_holes(model)
    spacing, margin, findings = check_hole_clearances(
        holes, bbox_min, bbox_max, thresholds)
    return EngineeringReport(
        bbox_min=bbox_min, bbox_max=bbox_max, bbox_size=bbox_size,
        volume=model.volume, surface_area=model.area,
        center_of_mass=_center_of_mass(model), hole_count=len(holes),
        min_hole_spacing_mm=spacing, min_edge_margin_mm=margin,
        dfm_findings=findings,
    )


def check_hole_clearances(
    holes: Sequence[Hole], bbox_min: tuple[float, float, float],
    bbox_max: tuple[float, float, float], thresholds: DfmThresholds | None = None,
) -> tuple[float | None, float | None, tuple[DfmFinding, ...]]:
    """Measure the hole clearances of a part and report the advisory findings.

    The first number is the smallest ligament between two non-coaxial holes and
    the second is the smallest wall between a hole and the edge of the part.
    """
    limits = thresholds if thresholds is not None else DfmThresholds()
    findings: list[DfmFinding] = []
    spacing = _min_ligament(holes, limits, findings)
    margin = _min_edge_margin(holes, bbox_min, bbox_max, limits, findings)
    return spacing, margin, tuple(findings)


def format_engineering_summary(report: EngineeringReport) -> str:
    """Return the engineering summary of a report as a compact text block.

    The block uses the dialect of the repair feedback: two spaces of indent,
    one decimal on every measured number and the unit after the value.
    """
    lines = [
        ENGINEERING_HEADER,
        f"{INDENT}bbox_min: {_size(report.bbox_min)} mm",
        f"{INDENT}bbox_max: {_size(report.bbox_max)} mm",
        f"{INDENT}bbox_size: {_size(report.bbox_size)} mm",
        f"{INDENT}volume: {_number(report.volume)} mm^3",
        f"{INDENT}surface_area: {_number(report.surface_area)} mm^2",
        f"{INDENT}center_of_mass: {_size(report.center_of_mass)} mm",
        f"{INDENT}holes: {report.hole_count}",
        f"{INDENT}min_hole_spacing: {_length(report.min_hole_spacing_mm)}",
        f"{INDENT}min_edge_margin: {_length(report.min_edge_margin_mm)}",
    ]
    if report.dfm_findings:
        lines.append(f"{INDENT}DFM findings:")
        for finding in report.dfm_findings:
            lines.append(
                f"{INDENT}{INDENT}{finding.code} ({finding.severity}): "
                f"{finding.message}")
    return "\n".join(lines)


def _min_ligament(
    holes: Sequence[Hole], limits: DfmThresholds, findings: list[DfmFinding],
) -> float | None:
    """Return the smallest ligament between two holes that are not coaxial."""
    smallest: float | None = None
    for index, first in enumerate(holes):
        for second in holes[index + 1:]:
            if _is_coaxial(first, second, limits.coaxial_tol_mm):
                continue
            ligament = _ligament(first, second)
            if smallest is None or ligament < smallest:
                smallest = ligament
            if ligament < 0.0:
                findings.append(DfmFinding(
                    DFM1, "error",
                    f"{_pair(first, second)} overlap: the ligament is "
                    f"{_number(ligament, 3)} mm"))
            elif ligament < limits.min_ligament_mm:
                findings.append(DfmFinding(
                    DFM2, "warning",
                    f"{_pair(first, second)} leave a ligament of "
                    f"{_number(ligament, 3)} mm, below the "
                    f"{_number(limits.min_ligament_mm, 3)} mm minimum"))
    return smallest


def _min_edge_margin(
    holes: Sequence[Hole], bbox_min: tuple[float, float, float],
    bbox_max: tuple[float, float, float], limits: DfmThresholds,
    findings: list[DfmFinding],
) -> float | None:
    """Return the smallest wall between a hole and the edge of the part."""
    smallest: float | None = None
    for hole in holes:
        radius = hole.diameter / 2
        margin = min(
            hole.x - radius - bbox_min[0],
            bbox_max[0] - (hole.x + radius),
            hole.y - radius - bbox_min[1],
            bbox_max[1] - (hole.y + radius),
        )
        if smallest is None or margin < smallest:
            smallest = margin
        if margin < limits.min_edge_margin_mm:
            findings.append(DfmFinding(
                DFM3, "warning",
                f"the hole at ({_number(hole.x)}, {_number(hole.y)}) leaves "
                f"{_number(margin, 3)} mm to the edge of the part, below the "
                f"{_number(limits.min_edge_margin_mm, 3)} mm minimum"))
    return smallest


def _ligament(first: Hole, second: Hole) -> float:
    """Return the edge-to-edge distance between two holes."""
    distance = math.hypot(second.x - first.x, second.y - first.y)
    return distance - (first.diameter / 2 + second.diameter / 2)


def _is_coaxial(first: Hole, second: Hole, tolerance: float) -> bool:
    """True when two holes stand on the same spot and are one stepped bore."""
    return math.hypot(second.x - first.x, second.y - first.y) <= tolerance


def _center_of_mass(model: StepModel) -> tuple[float, float, float]:
    """Return the mass centroid of the model, weighted by the volume.

    The centroid of a model with several solids is the mean of their centroids.
    """
    total = sum(solid.volume for solid in model.solids)
    if total <= 0.0:
        return (0.0, 0.0, 0.0)
    x = y = z = 0.0
    for solid in model.solids:
        point = solid.center(CenterOf.MASS)
        x += point.X * solid.volume
        y += point.Y * solid.volume
        z += point.Z * solid.volume
    return (x / total, y / total, z / total)


def _pair(first: Hole, second: Hole) -> str:
    """Return the two hole positions as one readable phrase."""
    return (f"the holes at ({_number(first.x)}, {_number(first.y)}) and "
            f"({_number(second.x)}, {_number(second.y)})")


def _number(value: float, places: int = 1) -> str:
    """Return a measured number with the given number of decimals."""
    return f"{value:.{places}f}"


def _size(size: tuple[float, float, float]) -> str:
    """Return three numbers as X, Y and Z."""
    return " x ".join(_number(value) for value in size)


def _length(value: float | None) -> str:
    """Return a measured length with its unit, or say it is not measured."""
    return "not measured" if value is None else f"{_number(value)} mm"
