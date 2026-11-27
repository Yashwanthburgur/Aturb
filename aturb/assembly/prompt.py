"""Compose the prompt of one assembly edit and parse the answer back.

The prompt is one clean text, built in a fixed order: the core instruction and
the output contract, the prompt of the pack, the project conventions, the
context of the assembly, the requested change and, on a repair attempt, the
feedback of the attempt before.

The answer is plain text. Every part that must change is wrapped in two exact
markers, and the parser is strict: an unknown part id, a duplicate part id, an
unclosed block, a mismatched end marker and an empty body are all refused.

The module is CAD-neutral: it names parts, mates and clearances, and no CAD
system.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from aturb.agent.params import extract_params, format_params_block
from aturb.agent.prompt import conventions_text, strip_code_fence
from aturb.assembly.manifest import AssemblyError, AssemblySpec
from aturb.verify.assembly import AssemblyReport

PART_START_PREFIX = "# === PART: "
PART_END_PREFIX = "# === END PART: "
PART_MARKER_SUFFIX = " ==="

FENCE = "```"

CORE_INSTRUCTION = """\
Edit the parts of one assembly. Return the complete new source of every part
that must change, and nothing else.

Output contract: emit ONLY the parts that must change, each one as a complete
source file, wrapped in these exact markers:

# === PART: <part_id> ===
<complete source for part_id>
# === END PART: <part_id> ===

Write no commentary outside the markers, emit no part that does not change and
emit no part id twice.
"""

EDITING_RULES = (
    "- Propagate a coupled dimensional change to every mating part, so the "
    "clearances and the mates stay valid.",
    "- Do not introduce interference between the components.",
    "- Preserve every unaffected feature, the origin, the axes and the "
    "parameter names.",
)


class AssemblyParseError(AssemblyError):
    """Raised when the answer of the model is not a valid set of part blocks."""


def compose_assembly_edit_prompt(
    spec: AssemblySpec,
    *,
    instruction: str,
    pack_prompt: str,
    part_sources: Mapping[str, str],
    report: AssemblyReport | None,
    feedback: str = "",
) -> str:
    """Return the prompt of one assembly edit.

    The sections come in a fixed order and are joined with one blank line
    between them: the core instruction and the output contract, the prompt of
    the pack, the project conventions, the context of the assembly, the
    requested change and the feedback of the attempt before. The output
    contract appears exactly once, in the first section.
    """
    sections = [CORE_INSTRUCTION]
    if pack_prompt.strip():
        sections.append(pack_prompt.strip())
    sections.append(conventions_text())
    sections.append(_context(spec, part_sources, report))
    sections.append(_request(instruction))
    if feedback.strip():
        sections.append(feedback.strip())
    return "\n\n".join(section.strip() for section in sections)


def parse_part_updates(text: str, allowed_part_ids: Collection[str]) -> dict[str, str]:
    """Return the new source of every part the answer updates.

    The answer is scanned line by line for the exact start and end markers of a
    part. A body that is wrapped in one code fence is unwrapped, and the
    source of every part ends with a newline.

    Raises ``AssemblyParseError`` when the answer holds no block, when a block
    is not closed, when an end marker closes another part, when a part id is
    not part of the assembly, when a part id appears twice or when a body is
    empty.
    """
    allowed = set(allowed_part_ids)
    body = strip_code_fence(text.strip())
    updates: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        started = _marker_id(line, PART_START_PREFIX)
        if started is not None:
            if current is not None:
                raise AssemblyParseError(
                    f"the part block {current!r} is not closed")
            if started not in allowed:
                raise AssemblyParseError(
                    f"the part {started!r} is not part of the assembly")
            if started in updates:
                raise AssemblyParseError(
                    f"the part {started!r} is updated twice")
            current = started
            lines = []
            continue
        ended = _marker_id(line, PART_END_PREFIX)
        if ended is not None:
            if current is None:
                raise AssemblyParseError(
                    f"the end marker of {ended!r} has no start marker")
            if ended != current:
                raise AssemblyParseError(
                    f"the end marker {ended!r} does not close the part "
                    f"{current!r}")
            source = strip_code_fence("\n".join(lines)).strip("\n")
            if not source.strip():
                raise AssemblyParseError(
                    f"the part {current!r} has an empty source")
            updates[current] = source + "\n"
            current = None
            lines = []
            continue
        if current is not None:
            lines.append(line)
    if current is not None:
        raise AssemblyParseError(f"the part block {current!r} is not closed")
    if not updates:
        raise AssemblyParseError("the answer holds no part block")
    return updates


def _context(spec: AssemblySpec, part_sources: Mapping[str, str],
             report: AssemblyReport | None) -> str:
    """Return the context block of the assembly: its parts and its measures."""
    lines = [f"Assembly: {spec.assembly_id} ({spec.name})", "Components:"]
    for component in spec.components:
        lines.append(
            f"- {component.name} (part_id={component.part_id}) at "
            f"position={_vector(component.position)} "
            f"rotation_deg={_vector(component.rotation_deg)}")
    if spec.mates:
        lines.append("Mates:")
        for mate in spec.mates:
            lines.append(
                f"- {mate.part_a} <-> {mate.part_b}: clearance "
                f"[{_number(mate.min_clearance_mm)}, "
                f"{_maximum(mate.max_clearance_mm)}] mm")
    if report is not None:
        lines.extend(_measurements(report))
    lines.append("Current parts:")
    for part_id in _part_ids(spec):
        lines.append(f"### Part {part_id}")
        source = part_sources.get(part_id, "")
        params = format_params_block(extract_params(source))
        if params:
            lines.append(params)
        lines.append(FENCE)
        lines.append(source.rstrip("\n"))
        lines.append(FENCE)
    return "\n".join(lines)


def _measurements(report: AssemblyReport) -> list[str]:
    """Return the verified measurements of the assembly, one per line."""
    lines = [
        "Current verified assembly measurements:",
        f"- total_volume = {report.total_volume:.6f} mm^3",
        f"- bbox_size = {_vector(report.bbox_size)} mm",
        f"- has_interference = {'yes' if report.has_interference else 'no'}",
    ]
    for pair in report.pairs:
        lines.append(
            f"- {pair.part_a} <-> {pair.part_b}: clearance = "
            f"{pair.min_clearance_mm:.3f} mm, overlap = "
            f"{pair.overlap_volume_mm3:.3f} mm^3")
    return lines


def _request(instruction: str) -> str:
    """Return the requested change and the rules of an assembly edit."""
    lines = [
        "Requested assembly change:",
        instruction.strip(),
        "",
        "Assembly editing rules:",
        *EDITING_RULES,
    ]
    return "\n".join(lines)


def _part_ids(spec: AssemblySpec) -> tuple[str, ...]:
    """Return the part ids of the assembly, each of them once, in order."""
    seen: list[str] = []
    for component in spec.components:
        if component.part_id not in seen:
            seen.append(component.part_id)
    return tuple(seen)


def _marker_id(line: str, prefix: str) -> str | None:
    """Return the part id of one marker line, or None when it is not one."""
    stripped = line.strip()
    if not stripped.startswith(prefix) or not stripped.endswith(PART_MARKER_SUFFIX):
        return None
    part_id = stripped[len(prefix):len(stripped) -
                       len(PART_MARKER_SUFFIX)].strip()
    return part_id or None


def _vector(values: tuple[float, float, float]) -> str:
    """Return three numbers as a readable list."""
    return "[" + ", ".join(repr(float(value)) for value in values) + "]"


def _number(value: float) -> str:
    """Return one number as a readable text."""
    return f"{float(value):g}"


def _maximum(value: float | None) -> str:
    """Return the top of a clearance window, or the text of an open one."""
    return "inf" if value is None else _number(value)
