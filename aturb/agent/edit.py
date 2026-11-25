"""Iterative editing of a verified workspace, one immutable revision at a time.

An edit takes the active revision of a workspace, asks the model for the
changed source of the part, and builds the answer into a brand-new revision
folder. The revision is promoted only when the exported geometry is a valid
single solid; a failed edit is recorded as a failure and the active revision
stays where it was.

The edit is expectation-free: the requirement holds the requested change, the
measured facts of the current part and the current source, and nothing else.
No task, no answer and no score ever reaches the model.

The module is CAD-neutral: it knows about manifests, folders and relative
paths, and about nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from aturb.agent.generate import DEFAULT_PART_ID, GenerateResult, generate_part
from aturb.agent.generate_cli import write_generate_manifest
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
from aturb.workspace.paths import PathEscapeError, resolve_inside

MEASURED_FIELDS = ("volume", "bbox_size", "hole_count", "holes")
EDITING_RULES = (
    "- Modify the existing part to apply ONLY the requested change.",
    "- Preserve every unaffected feature, dimension, parameter name, the "
    "coordinate origin and axes, and the design intent.",
    "- Return the complete updated source file.",
)


@dataclass(frozen=True)
class EditResult:
    """The outcome of one edit of a workspace.

    ``revision_id`` is the revision the edit built and ``parent_revision``
    is the revision it was built from. ``promoted`` says whether the new
    revision became the active one, and ``active_revision`` names the
    revision that is active after the edit.
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
) -> str:
    """Return the requirement of one edit of a verified part.

    The requirement holds four blocks: the requested change, the measured
    facts of the current part, the current source and the rules of the edit.
    The facts are the ones the manifest records, so they come from an
    independent check of the exported geometry and not from an assumption.
    """
    return "\n".join([
        "Requested change:",
        instruction.strip(),
        "",
        "Current verified part - measured facts (from an independent STEP "
        "check, not assumptions):",
        _facts(current_manifest),
        "",
        "Current verified source code:",
        current_source,
        "",
        "Editing rules:",
        *EDITING_RULES,
    ])


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

    The workspace is bootstrapped into a history when it has none, so a
    plain verified workspace becomes editable on the first edit. An empty
    instruction is refused before anything is written.

    A model or build failure is not an exception: the failed revision is
    recorded, the active revision stays where it was, and the result says
    what went wrong.
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
    part_id = str(manifest.get("part_id") or DEFAULT_PART_ID)
    revision_id = next_revision_id(workspace, history)
    revision_dir = workspace / REVISIONS_DIR_NAME / revision_id
    requirement = compose_edit_requirement(instruction, source, manifest)
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
             if key in manifest]
    return "\n".join(lines) if lines else "(no measured facts are recorded)"


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
