"""Iterative editing of a verified workspace, one immutable revision at a time.

An edit takes the active revision of a workspace, asks the model for the
changed source of the part, and builds the answer into a brand-new revision
folder. The revision is promoted only when the exported geometry is a valid
single solid; a failed edit is a failure and the active revision stays put.

The edit is expectation-free: the requirement holds the requested change, the
measured facts, the engineering measurements, the parameters and the source.
No task, no answer and no score ever reaches the model.

The module is CAD-neutral: it knows about manifests, folders and paths.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypeGuard

from aturb.agent.generate import DEFAULT_PART_ID, GenerateResult, generate_part
from aturb.agent.generate_cli import write_generate_manifest
from aturb.agent.params import extract_params, format_params_block
from aturb.agent.revisions import (
    MANIFEST_FILE_NAME,
    REVISIONS_DIR_NAME,
    RevisionEntry,
    RevisionError,
    active_revision_dir,
    ensure_history,
    is_verified_manifest,
    next_revision_id,
    read_manifest,
    write_history,
)
from aturb.agent.types import ModelClient
from aturb.contract.runner import Runner
from aturb.packs import PackManifest
from aturb.verify.engineering import (
    EngineeringReport,
    analyze_step,
    format_engineering_summary,
)
from aturb.verify.step import StepLoadError
from aturb.workspace.paths import PathEscapeError, resolve_inside

MEASURED_FIELDS = ("volume", "bbox_size", "hole_count", "holes")
ENGINEERING_HEADER = "Current engineering measurements (from STEP):"
EDITING_RULES = (
    "- Modify the existing part to apply ONLY the requested change.",
    "- Propagate a coupled dimensional change to every parameter and every "
    "clearance that depends on it.",
    "- Keep the clearances and do not introduce a DFM violation (DFM1, DFM2 or DFM3).",
    "- Preserve every unaffected feature, dimension, parameter name, the "
    "coordinate origin and axes, and the design intent.",
)


@dataclass(frozen=True)
class EditResult:
    """The outcome of one edit of a workspace.

    ``revision_id`` is the revision the edit built, ``parent_revision`` is the
    revision it was built from, and ``promoted`` says whether the new revision
    became the active one.
    """

    status: str
    revision_id: str
    parent_revision: str
    active_revision: str
    promoted: bool
    revision_dir: Path
    generate: GenerateResult
    error: str


def compose_edit_requirement(
    instruction: str,
    current_source: str,
    current_manifest: dict,
    engineering: EngineeringReport | None = None,
) -> str:
    """Return the requirement of one edit of a verified part.

    The requirement holds the requested change, the measured facts of the
    current part, the engineering measurements of the exported STEP, the
    parameters of the current source, the current source and the rules of the
    edit. The facts are the ones the manifest records and the measurements are
    the ones the exported STEP gives, so they come from an independent check
    of the exported geometry and not from an assumption.
    """
    blocks = [
        "Requested change:",
        instruction.strip(),
        "",
        "Current verified part - measured facts (from an independent STEP "
        "check, not assumptions):",
        _facts(current_manifest),
    ]
    if engineering is not None:
        blocks.extend([
            "",
            ENGINEERING_HEADER,
            format_engineering_summary(engineering),
        ])
    params = format_params_block(extract_params(current_source))
    if params:
        blocks.extend(["", params])
    blocks.extend([
        "",
        "Current verified source code:",
        current_source,
        "",
        "Editing rules:",
        *EDITING_RULES,
    ])
    return "\n".join(blocks)


def edit_part(
    workspace_dir: Path,
    instruction: str,
    client: ModelClient,
    runner: Runner,
    settings: dict,
    pack: PackManifest,
    timeout_s: int,
) -> EditResult:
    """Edit the active revision of a workspace and record the outcome.

    The workspace is bootstrapped into a history when it has none, so a plain
    verified workspace becomes editable on the first edit. An empty instruction
    is refused before anything is written. A model or build failure is not an
    exception: the failed revision is recorded and the active revision stays.
    """
    if not isinstance(instruction, str) or not instruction.strip():
        raise RevisionError("the edit instruction is empty")
    workspace = Path(workspace_dir)
    history = ensure_history(workspace)
    parent_id = history.active_revision
    parent_dir = active_revision_dir(workspace)
    manifest = read_manifest(parent_dir / MANIFEST_FILE_NAME)
    if not is_verified_manifest(manifest, parent_dir):
        raise RevisionError(
            f"the active revision {parent_id!r} holds no verified part")
    source = _read_source(parent_dir, manifest)
    engineering = _engineering(parent_dir, manifest)
    part_id = str(manifest.get("part_id") or DEFAULT_PART_ID)
    revision_id = next_revision_id(workspace, history)
    revision_dir = workspace / REVISIONS_DIR_NAME / revision_id
    requirement = compose_edit_requirement(
        instruction, source, manifest, engineering=engineering)
    generated = generate_part(
        requirement=requirement, out_dir=revision_dir, client=client,
        runner=runner, settings=settings, pack=pack, timeout_s=timeout_s,
        part_id=part_id)
    error = generated.error
    try:
        write_generate_manifest(generated)
    except (OSError, ValueError) as exc:
        error = f"the manifest of the revision could not be written: {exc}"
        promoted = False
    else:
        promoted = _is_promoted(generated)
    entry = RevisionEntry(
        id=revision_id, parent=parent_id, kind="edit",
        status="ok" if promoted else "error",
        stop_reason=generated.stop_reason, instruction=instruction.strip(),
        attempts=generated.attempts, prompt_version=generated.prompt_version,
        rel_dir=f"{REVISIONS_DIR_NAME}/{revision_id}")
    updated = replace(
        history, revisions=history.revisions + (entry,),
        active_revision=revision_id if promoted else parent_id)
    write_history(workspace, updated)
    return EditResult(
        status="ok" if promoted else "error", revision_id=revision_id,
        parent_revision=parent_id, active_revision=updated.active_revision,
        promoted=promoted, revision_dir=revision_dir, generate=generated,
        error=error)


def _is_promoted(generated: GenerateResult) -> bool:
    """True when a generation holds a valid single solid and may be promoted."""
    return (generated.status == "ok"
            and generated.geometry is not None
            and generated.geometry.is_valid
            and generated.geometry.is_single_solid)


def _facts(manifest: dict) -> str:
    """Return the measured facts of a manifest, one per line."""
    lines = [f"{key}: {manifest[key]}" for key in MEASURED_FIELDS
             if key in manifest and key != "holes"]
    if "holes" in manifest:
        lines.append("holes:")
        lines.extend(_holes(manifest["holes"]))
    return "\n".join(lines) if lines else "(no measured facts are recorded)"


def _holes(holes: object) -> list[str]:
    """Return the holes of a manifest, one per line, as readable facts."""
    if not isinstance(holes, list):
        return []
    lines = []
    for index, hole in enumerate(holes, start=1):
        if not isinstance(hole, dict):
            continue
        diameter = hole.get("diameter")
        x = hole.get("x")
        y = hole.get("y")
        if not (_is_number(diameter) and _is_number(x) and _is_number(y)):
            continue
        lines.append(
            f"- hole {index}: diameter {diameter:.1f} mm, "
            f"position ({x:.1f}, {y:.1f}) mm")
    return lines


def _is_number(value: object) -> TypeGuard[float]:
    """True when the value is a number and not a boolean."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _engineering(revision_dir: Path, manifest: dict) -> EngineeringReport | None:
    """Return the engineering report of the exported STEP of a revision.

    The report is None when the revision names no STEP file, when the file is
    not inside the revision or when it cannot be read as a model.
    """
    step_file = manifest.get("step_file")
    if not isinstance(step_file, str) or not step_file.strip():
        return None
    try:
        step_path = resolve_inside(revision_dir, step_file)
        if not step_path.is_file():
            return None
        return analyze_step(step_path)
    except StepLoadError:
        return None
    except Exception:
        # A measurement is an advisory: it never stops the edit.
        return None


def _read_source(revision_dir: Path, manifest: dict) -> str:
    """Return the source of a revision, read from inside its folder."""
    part_file = manifest.get("part_file")
    if not isinstance(part_file, str) or not part_file.strip():
        raise RevisionError("the active revision names no source file")
    try:
        target = resolve_inside(revision_dir, part_file)
    except (PathEscapeError, OSError, ValueError) as exc:
        raise RevisionError(
            "the source of the active revision is not inside it") from exc
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RevisionError(
            f"the source of the active revision cannot be read: {exc}") from exc
