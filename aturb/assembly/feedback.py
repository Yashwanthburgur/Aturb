"""Render the repair feedback of one assembly attempt as a text block.

The block tells the agent what its own update did: the format error of the
answer, the build error of a part that failed, and the interference volume and
the mate clearance of a pair that failed. It never carries an evaluator value:
no expected value, no tolerance and no score.

The module is CAD-neutral: it names parts, pairs and clearances, and no CAD
system.
"""

from __future__ import annotations

from collections.abc import Mapping

from aturb.assembly.build import AssemblyBuildResult

MAX_PAIR_ISSUES = 8  # starting default
MAX_DIAGNOSTICS = 6  # starting default

HEADER = "## Assembly Repair"
INSTRUCTION = (
    "The previous update was NOT promoted. Fix the failures below and emit the "
    "updated part blocks using the exact PART markers."
)
MARKER_EXAMPLE = (
    "# === PART: <part_id> ===\n"
    "<complete source for part_id>\n"
    "# === END PART: <part_id> ==="
)
FENCE = "```"


def assembly_feedback_text(
    *,
    parse_error: str = "",
    build: AssemblyBuildResult | None = None,
    previous_updates: Mapping[str, str] | None = None,
) -> str:
    """Return the repair feedback block of one assembly attempt.

    The block names the format error of the answer, the parts that failed to
    build, the pairs that interfere or that break a mate, and the part updates
    of the attempt before. The lists are capped, so a long failure never makes
    the prompt unreadable.
    """
    sections = [HEADER, INSTRUCTION]
    if parse_error.strip():
        sections.append(
            f"Format error:\n{parse_error.strip()}\n\n{MARKER_EXAMPLE}")
    if build is not None:
        sections.extend(_build_sections(build))
    if previous_updates:
        sections.append(_previous(previous_updates))
    return "\n\n".join(sections)


def _build_sections(build: AssemblyBuildResult) -> list[str]:
    """Return the sections that describe what the build of the update did."""
    parts = _failing_parts(build)
    pairs = _failing_pairs(build)
    sections: list[str] = []
    if parts:
        sections.append("Failing part builds:\n" + "\n".join(parts))
    if pairs:
        sections.append("Failing assembly checks:\n" + "\n".join(pairs))
    if not parts and not pairs and build.error.strip():
        sections.append(f"Error: {build.error.strip()}")
    return sections


def _failing_parts(build: AssemblyBuildResult) -> list[str]:
    """Return one block per part of the assembly that failed to build."""
    lines: list[str] = []
    for part_id, result in build.part_results.items():
        if result.status == "ok":
            continue
        kind = result.failure_kind.value if result.failure_kind else "unknown"
        lines.append(f"- {part_id}: failure_kind={kind}")
        error = _first_line(result.error_text)
        if error:
            lines.append(f"  error: {error}")
        diagnostics = list(result.native_diagnostics.items())[:MAX_DIAGNOSTICS]
        for key, value in diagnostics:
            lines.append(f"  {key}: {value}")
    return lines


def _failing_pairs(build: AssemblyBuildResult) -> list[str]:
    """Return one line per pair that interferes or that breaks a mate."""
    report = build.report
    if report is None:
        return []
    lines: list[str] = []
    for pair in report.pairs:
        if not pair.intersects and pair.mate_ok:
            continue
        if len(lines) >= MAX_PAIR_ISSUES:
            break
        lines.append(
            f"- {pair.part_a} <-> {pair.part_b}: "
            f"intersects={'yes' if pair.intersects else 'no'}, "
            f"overlap={pair.overlap_volume_mm3:.3f} mm^3, "
            f"min_clearance={pair.min_clearance_mm:.3f} mm ({pair.note})")
    return lines


def _previous(previous_updates: Mapping[str, str]) -> str:
    """Return the part updates of the attempt before, with their sources."""
    lines = ["Previous attempted part updates:"]
    for part_id, source in previous_updates.items():
        lines.append(f"### Part {part_id}")
        lines.append(FENCE)
        lines.append(source.rstrip("\n"))
        lines.append(FENCE)
    return "\n".join(lines)


def _first_line(text: str) -> str:
    """Return the first line of a text, or the text when it has one line."""
    lines = text.splitlines()
    return lines[0].strip() if lines else ""
