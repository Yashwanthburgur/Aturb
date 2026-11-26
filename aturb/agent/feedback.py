"""Render the repair feedback of one attempt as a text block.

The block tells the agent what its own candidate did: the outcome of the
build, the sanitized error text and the traceback, the advisory findings of
the candidate, the candidate-only geometry summary measured from the exported
STEP of the candidate and the source code of the candidate itself.

The advisory findings are the engineering findings measured from the exported
STEP of the candidate, the diagnostics of the build and the convention findings
of the source. They are ranked, the errors come before the warnings, and the
list is capped. Without a STEP path the block keeps its earlier shape.

It never carries an evaluator-derived field: no expected value, no tolerance,
no check name, no verdict, no evaluator message, no score and no expectation
content. The formatter takes candidate-side inputs only, and the module is
CAD-neutral: it names no CAD, no CAD API and no backend.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aturb.evals.judge import CandidateGeometry
from aturb.verify.engineering import DfmFinding, analyze_step
from aturb.verify.step import StepLoadError
from aturb.workspace.paths import PathEscapeError, resolve_inside

HEADER = "## Repair"

REPAIR_INSTRUCTION = (
    "The previous file is replaced by the file you write now. "
    "The answer is still only the file."
)

GEOMETRY_HEADER = "Candidate geometry (measured from the exported STEP):"

ADVISORY_HEADER = "Advisory findings:"

PREVIOUS_HEADER = "Previous candidate:"

FENCE = "```"

INDENT = "  "

MAX_ADVISORY_FINDINGS = 8  # starting default


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
    previous_code: str = "",
    step_path: Path | None = None,
) -> str:
    """Return the repair feedback block of one attempt, or an empty text.

    The six inputs are candidate-side: the outcome of the build, the
    diagnostics, the convention findings, the geometry summary, the source code
    of the previous candidate and the exported STEP of that candidate. No
    parameter carries an evaluator value, so the rendered text stays clean.

    The sections come in the order of the contract: the repair instruction, the
    build outcome, the error text and the traceback, the advisory findings, the
    geometry summary and the previous candidate. An empty section is left out.
    """
    sections: list[str] = []
    if build is not None:
        _add(sections, _build_outcome(build))
        if build.error_text.strip():
            _add(sections, f"Error:\n{build.error_text.strip()}")
        if build.traceback.strip():
            _add(sections, f"Traceback:\n{build.traceback.strip()}")
    advisories = _advisories(build, diagnostics, conventions, step_path)
    if advisories is None:
        _add(sections, _listed("Diagnostics:", diagnostics))
        _add(sections, _listed("Convention findings:", conventions))
    else:
        _add(sections, _advisory_section(advisories))
    if build is not None and build.status == "ok" and geometry is not None:
        _add(sections, _geometry(geometry))
    _add(sections, _previous(previous_code))
    if not sections:
        return ""
    return "\n\n".join([HEADER, REPAIR_INSTRUCTION, *sections])


def candidate_step(project: Path, part_id: str) -> Path | None:
    """Return the exported STEP of the candidate, when the build produced one."""
    out_dir = Path(project) / "out" / part_id
    steps = sorted(out_dir.glob("*.step")) if out_dir.is_dir() else []
    if not steps:
        return None
    try:
        return resolve_inside(project, steps[0].relative_to(project))
    except (PathEscapeError, OSError, ValueError):
        return None


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
    return f"Build: {status} ({kind})" if kind else f"Build: {status}"


def _listed(label: str, items: Sequence[str]) -> str:
    """Return a labelled list of lines, one item per line."""
    kept = [item.strip() for item in items if item.strip()]
    if not kept:
        return ""
    lines = [label]
    lines.extend(f"{INDENT}{item}" for item in kept)
    return "\n".join(lines)


def _advisories(
    build: BuildFeedback | None, diagnostics: Sequence[str],
    conventions: Sequence[str], step_path: Path | None,
) -> list[tuple[int, str]] | None:
    """Return the ranked advisory items, or None when the block keeps its shape."""
    if step_path is None:
        return None
    items: list[tuple[int, str]] = []
    for finding in _dfm_findings(build, step_path):
        rank = 0 if finding.severity.strip().lower() == "error" else 1
        items.append(
            (rank, f"{finding.code} ({finding.severity}): {finding.message}"))
    for rank, group in ((2, diagnostics), (3, conventions)):
        for item in group:
            text = item.strip()
            if text:
                items.append((rank, text))
    return items


def _dfm_findings(build: BuildFeedback | None, step_path: Path | None) -> tuple[DfmFinding, ...]:
    """Return the advisory engineering findings of the exported STEP."""
    if build is None or build.status != "ok" or step_path is None:
        return ()
    try:
        if not Path(step_path).is_file():
            return ()
        return analyze_step(Path(step_path)).dfm_findings
    except StepLoadError:
        return ()
    except Exception:
        # An advisory finding never breaks the repair.
        return ()


def _advisory_section(items: Sequence[tuple[int, str]]) -> str:
    """Return the ranked and capped section of the advisory findings."""
    if not items:
        return ""
    ranked = sorted(items, key=lambda item: item[0])
    kept = ranked[:MAX_ADVISORY_FINDINGS]
    hidden = len(ranked) - len(kept)
    lines = [ADVISORY_HEADER]
    lines.extend(f"{INDENT}{text}" for _, text in kept)
    if hidden:
        lines.append(f"{INDENT}... and {hidden} more advisory finding(s)")
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


def _previous(code: str) -> str:
    """Return the source code of the previous candidate, fenced and verbatim."""
    text = code.strip()
    if not text:
        return ""
    fence = _fence(text)
    return f"{PREVIOUS_HEADER}\n\n{fence}\n{text}\n{fence}"


def _fence(text: str) -> str:
    """Return a fence of backticks that no line of the text can close."""
    longest = 0
    run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def _boolean(value: bool) -> str:
    """Return a boolean as the text of the block."""
    return "true" if value else "false"


def _number(value: float) -> str:
    """Return a measured number with one decimal."""
    return f"{value:.1f}"


def _size(size: tuple[float, float, float]) -> str:
    """Return the size of the bounding box as X, Y and Z."""
    return " x ".join(_number(value) for value in size)
