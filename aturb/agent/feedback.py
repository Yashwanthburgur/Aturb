"""Render the repair feedback of one attempt as a text block.

The block tells the agent what its own candidate did: the outcome of the
build, the sanitized error text and the traceback, the informational
diagnostics, the advisory convention findings and the candidate-only geometry
summary measured from the exported STEP of the candidate.

It never carries an evaluator-derived field: no expected value, no tolerance,
no check name, no verdict, no evaluator message, no score and no expectation
content. The formatter takes candidate-side inputs only, so an evaluator value
cannot reach the rendered text even by accident.

The module is CAD-neutral: it names no CAD, no CAD API and no backend.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aturb.evals.judge import CandidateGeometry

HEADER = "## Repair"

REPAIR_INSTRUCTION = (
    "The previous file is replaced by the file you write now. "
    "The answer is still only the file."
)

GEOMETRY_HEADER = "Candidate geometry (measured from the exported STEP):"

INDENT = "  "


@dataclass(frozen=True)
class BuildFeedback:
    """The outcome of the build of one candidate, in candidate-side terms.

    The status says whether the candidate built, the failure kind says how it
    failed, and the error text and the traceback say what went wrong. The text
    is already sanitized: it holds no absolute path and no drive letter.
    """

    status: str
    failure_kind: str = ""
    error_text: str = ""
    traceback: str = ""


def feedback_text(
    build: BuildFeedback | None,
    diagnostics: Sequence[str] = (),
    conventions: Sequence[str] = (),
    geometry: CandidateGeometry | None = None,
) -> str:
    """Return the repair feedback block of one attempt, or an empty text.

    The four inputs are candidate-side: the outcome of the build, the
    informational diagnostics, the advisory convention findings and the
    candidate-only geometry summary. There is no parameter for an expectation
    path, an expectation dictionary or an answer spec, so an evaluator value
    cannot reach the rendered text.

    The sections come in the order of the contract: the repair instruction, the
    build outcome, the error text and the traceback, the diagnostics, the
    convention findings and the geometry summary. A section with nothing to say
    is left out, and a block with nothing to say is an empty text.
    """
    sections: list[str] = []
    if build is not None:
        _add(sections, _build_outcome(build))
        if build.error_text.strip():
            _add(sections, f"Error:\n{build.error_text.strip()}")
        if build.traceback.strip():
            _add(sections, f"Traceback:\n{build.traceback.strip()}")
    _add(sections, _listed("Diagnostics:", diagnostics))
    _add(sections, _listed("Convention findings:", conventions))
    if build is not None and build.status == "ok" and geometry is not None:
        _add(sections, _geometry(geometry))
    if not sections:
        return ""
    return "\n\n".join([HEADER, REPAIR_INSTRUCTION, *sections])


def _add(sections: list[str], section: str) -> None:
    """Add a section to the block when it has something to say."""
    if section:
        sections.append(section)


def _build_outcome(build: BuildFeedback) -> str:
    """Return the line that says how the build went."""
    status = build.status.strip()
    if not status:
        return ""
    kind = build.failure_kind.strip()
    if kind:
        return f"Build: {status} ({kind})"
    return f"Build: {status}"


def _listed(label: str, items: Sequence[str]) -> str:
    """Return a labelled list of lines, one item per line."""
    kept = [item.strip() for item in items if item.strip()]
    if not kept:
        return ""
    lines = [label]
    lines.extend(f"{INDENT}{item}" for item in kept)
    return "\n".join(lines)


def _geometry(geometry: CandidateGeometry) -> str:
    """Return the candidate-only geometry summary of the exported STEP."""
    lines = [
        GEOMETRY_HEADER,
        f"{INDENT}is_valid: {_boolean(geometry.is_valid)}",
        f"{INDENT}is_single_solid: {_boolean(geometry.is_single_solid)}",
        f"{INDENT}volume: {_number(geometry.volume)} mm^3",
        f"{INDENT}bbox_size: {_size(geometry.bbox_size)} mm",
        f"{INDENT}holes: {len(geometry.holes)}",
    ]
    for index, hole in enumerate(geometry.holes, start=1):
        lines.append(
            f"{INDENT}{INDENT}hole {index}: diameter {_number(hole.diameter)} mm, "
            f"position ({_number(hole.x)}, {_number(hole.y)}) mm")
    return "\n".join(lines)


def _boolean(value: bool) -> str:
    """Return a boolean as the text of the block."""
    return "true" if value else "false"


def _number(value: float) -> str:
    """Return a measured number with one decimal."""
    return f"{value:.1f}"


def _size(size: tuple[float, float, float]) -> str:
    """Return the size of the bounding box as X, Y and Z."""
    return " x ".join(_number(value) for value in size)
