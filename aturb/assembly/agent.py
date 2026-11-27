"""The bounded assembly edit loop of the core.

The loop asks the model for the new source of the parts that must change,
parses the answer, applies the change through the safe assembly edit and
reports what happened. A rejected change is never promoted: the live project
stays byte-for-byte as it was, and the next attempt carries the exact failures
of the attempt before it.

The module is CAD-neutral: it names parts, mates and clearances, and no CAD
system.
"""

from __future__ import annotations

import math
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from aturb.agent.config import DEFAULTS, agent_settings
from aturb.agent.types import AgentError, ModelClient, ModelRequest
from aturb.assembly.build import AssemblyBuildResult, build_assembly
from aturb.assembly.edit import _part_file, apply_assembly_edit
from aturb.assembly.feedback import assembly_feedback_text
from aturb.assembly.manifest import AssemblyError, AssemblySpec, load_assembly
from aturb.assembly.prompt import (
    AssemblyParseError,
    _part_ids,
    compose_assembly_edit_prompt,
    parse_part_updates,
)
from aturb.assembly.revisions import ensure_assembly_history, record_assembly_revision
from aturb.contract.runner import Runner
from aturb.verify.assembly import AssemblyReport
from aturb.workspace.paths import PathEscapeError, resolve_inside, to_rel

PARTS_DIR = "parts"
CHARS_PER_TOKEN = 4  # starting default
TOKENS_PER_MTOK = 1_000_000


@dataclass(frozen=True)
class AssemblyAgentResult:
    """The outcome of one assembly edit.

    The status is ``ok`` when the change was promoted and ``failed`` when it
    was not; the stop reason says why the loop ended.
    """

    status: str
    stop_reason: str
    promoted: bool
    assembly_id: str
    attempts: int
    updated_parts: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    build: AssemblyBuildResult | None
    error: str
    revision_id: str = ""
    parent_revision: str = ""


def edit_assembly(
    project_root: Path,
    assembly_path: Path,
    instruction: str,
    *,
    client: ModelClient,
    runner: Runner,
    settings: dict,
    pack_prompt: str = "",
    timeout_s: int = 60,  # starting default
    record_revision: bool = False,
) -> AssemblyAgentResult:
    """Edit the parts of an assembly and promote the change when it verifies.

    The baseline of the assembly is verified first, so an edit never starts
    from a broken assembly. Every attempt composes one prompt, calls the model
    once and applies the answer through the safe assembly edit. A rejected
    answer becomes the feedback of the next attempt, and the loop ends when
    the change is promoted, when a budget is passed, when the model fails or
    when the attempt limit is reached. The ``record_revision`` flag asks for
    the revision of the assembly to be recorded.
    """
    if not isinstance(instruction, str) or not instruction.strip():
        return _failed("", "preparation_error", "the instruction is empty")
    project_root = Path(project_root).resolve()
    try:
        spec = load_assembly(resolve_inside(project_root, assembly_path))
    except (AssemblyError, PathEscapeError, OSError, ValueError) as exc:
        return _failed("", "preparation_error", str(exc))
    assembly_id = spec.assembly_id
    try:
        sources = _part_sources(project_root, spec)
        report = _baseline(project_root, assembly_path, runner, timeout_s)
        values = agent_settings({"agent": settings})
        max_attempts = int(_limit(values, "max_attempts"))
        max_output = int(_limit(values, "max_output_tokens"))
        model = str(values.get("model", ""))
        parent_revision = ""
        if record_revision:
            history = ensure_assembly_history(
                project_root, assembly_path, spec)
            parent_revision = str(history.get("active_revision", ""))
    except (AgentError, AssemblyError, PathEscapeError, OSError, ValueError) as exc:
        return _failed(assembly_id, "preparation_error", str(exc))

    feedback = ""
    last_error = ""
    attempts = 0
    input_tokens = 0
    output_tokens = 0
    cost_usd = 0.0

    def record(result: AssemblyAgentResult) -> AssemblyAgentResult:
        """Record the revision of the assembly, when one was asked for."""
        if not record_revision:
            return result
        entry = record_assembly_revision(
            project_root, assembly_path, spec, kind="edit",
            status="ok" if result.promoted else "failed",
            stop_reason=result.stop_reason, instruction=instruction.strip(),
            attempts=result.attempts, updated_parts=result.updated_parts,
            promote=result.promoted)
        return replace(result, revision_id=str(entry.get("id", "")),
                       parent_revision=parent_revision)

    def failed(reason: str, error: str) -> AssemblyAgentResult:
        """Return a failed edit that promoted nothing."""
        return record(AssemblyAgentResult(
            status="failed", stop_reason=reason, promoted=False,
            assembly_id=assembly_id, attempts=attempts, updated_parts=(),
            input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost_usd, build=None, error=error))

    for attempt in range(1, max_attempts + 1):
        prompt = compose_assembly_edit_prompt(
            spec, instruction=instruction, pack_prompt=pack_prompt,
            part_sources=sources, report=report, feedback=feedback)
        estimated = math.ceil(len(prompt) / CHARS_PER_TOKEN)
        refusal = _budget_error(
            estimated, values, input_tokens, output_tokens, cost_usd)
        if refusal:
            return failed("budget_exceeded", refusal)
        attempts = attempt
        try:
            response = client.complete(ModelRequest(
                prompt=prompt, model=model, max_output_tokens=max_output))
        except AgentError as exc:
            return failed("model_error", str(exc))
        input_tokens += response.input_tokens
        output_tokens += response.output_tokens
        cost_usd += _cost_of(response.input_tokens,
                             response.output_tokens, values)
        try:
            updates = parse_part_updates(response.text, tuple(sources))
        except AssemblyParseError as exc:
            last_error = str(exc)
            feedback = assembly_feedback_text(parse_error=last_error)
            continue
        try:
            edit = apply_assembly_edit(
                project_root, assembly_path, updates, runner, timeout_s=timeout_s)
        except AssemblyError as exc:
            last_error = str(exc)
            feedback = assembly_feedback_text(parse_error=last_error)
            continue
        if edit.promoted:
            return record(AssemblyAgentResult(
                status="ok", stop_reason="built", promoted=True,
                assembly_id=assembly_id, attempts=attempts,
                updated_parts=edit.updated_parts, input_tokens=input_tokens,
                output_tokens=output_tokens, cost_usd=cost_usd,
                build=edit.build, error=""))
        last_error = edit.error
        feedback = assembly_feedback_text(
            build=edit.build, previous_updates=updates)
    return failed("max_attempts",
                  last_error or "the assembly edit did not verify")


def _part_sources(project_root: Path, spec: AssemblySpec) -> dict[str, str]:
    """Return the source of every unique part of the assembly."""
    parts_dir = resolve_inside(project_root, PARTS_DIR)
    sources: dict[str, str] = {}
    for part_id in _part_ids(spec):
        path = _part_file(parts_dir, part_id)
        sources[part_id] = path.read_text(encoding="utf-8")
    return sources


def _baseline(project_root: Path, assembly_path: Path, runner: Runner,
              timeout_s: int) -> AssemblyReport:
    """Return the verified report of the assembly as it stands now.

    The baseline is built in a staging copy of the project, so the live
    project is never written by the preparation of an edit. A baseline that
    does not verify is refused, so an edit never starts from a broken
    assembly.
    """
    relative = to_rel(project_root, resolve_inside(
        project_root, assembly_path))
    with tempfile.TemporaryDirectory(prefix="aturb-assembly-base-") as staging:
        staging_root = Path(staging) / "project"
        shutil.copytree(project_root, staging_root)
        built = build_assembly(
            staging_root, Path(relative), runner, timeout_s=timeout_s)
    if built.status != "ok" or built.report is None:
        raise AssemblyError(
            f"the baseline assembly does not verify: {built.error}")
    return built.report


def _limit(values: dict, key: str) -> float:
    """Return one limit of the agent settings as a number."""
    value = values.get(key, DEFAULTS.get(key, 0))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the agent setting {key!r} must be a number")
    if value < 0:
        raise ValueError(f"the agent setting {key!r} cannot be negative")
    return float(value)


def _cost_of(input_tokens: int, output_tokens: int, values: dict) -> float:
    """Return the cost of one call in dollars, from the configured prices."""
    price_in = _limit(values, "input_price_per_mtok")
    price_out = _limit(values, "output_price_per_mtok")
    return (input_tokens * price_in + output_tokens * price_out) / TOKENS_PER_MTOK


def _budget_error(estimated: int, values: dict, used_input: int,
                  used_output: int, used_cost: float) -> str:
    """Say why the next call is not allowed, or nothing when it is."""
    max_input = int(_limit(values, "max_input_tokens"))
    max_output = int(_limit(values, "max_output_tokens"))
    total_input = int(_limit(values, "max_total_input_tokens"))
    total_output = int(_limit(values, "max_total_output_tokens"))
    max_cost = _limit(values, "max_cost_usd")
    total_cost = _limit(values, "max_total_cost_usd")
    if estimated > max_input:
        return (f"the prompt is over the input token cap: {estimated} tokens "
                f"> {max_input:g}")
    if used_input + estimated > total_input:
        return (f"the cumulative input token budget would be passed: "
                f"{used_input + estimated} tokens > {total_input}")
    if used_output + max_output > total_output:
        return (f"the cumulative output token budget would be passed: "
                f"{used_output + max_output} tokens > {total_output}")
    cost = _cost_of(estimated, max_output, values)
    if cost > max_cost:
        return (f"the call would pass the cost budget: {cost:.6f} USD > "
                f"{max_cost:.6f} USD")
    if used_cost + cost > total_cost:
        return (f"the cumulative cost budget would be passed: "
                f"{used_cost + cost:.6f} USD > {total_cost:.6f} USD")
    return ""


def _failed(assembly_id: str, stop_reason: str, error: str) -> AssemblyAgentResult:
    """Return a failed edit that promoted nothing."""
    return AssemblyAgentResult(
        status="failed", stop_reason=stop_reason, promoted=False,
        assembly_id=assembly_id, attempts=0, updated_parts=(), input_tokens=0,
        output_tokens=0, cost_usd=0.0, build=None, error=error)
