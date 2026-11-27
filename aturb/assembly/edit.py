"""Apply a change to the parts of an assembly without breaking the assembly.

The change is built and verified in an isolated staging copy of the project.
Only a change whose whole assembly verifies is promoted into the live project,
and the promotion is atomic. A rejected change leaves the live project exactly
as it was: every part source file and every output of the assembly.

A change to several parts is one change. It is verified as one assembly, so a
change that only works together is never promoted one part at a time.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from aturb.assembly.build import AssemblyBuildResult, build_assembly
from aturb.assembly.manifest import AssemblyError
from aturb.contract.runner import Runner
from aturb.workspace.io import atomic_write_text
from aturb.workspace.paths import PathEscapeError, resolve_inside, to_rel

PARTS_DIR = "parts"
PART_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class AssemblyEditResult:
    """The outcome of one assembly edit.

    The `updated_parts` names the parts that were written into the live
    project. A rejected edit writes nothing, so it names no part at all.
    """

    status: str
    promoted: bool
    assembly_id: str
    updated_parts: tuple[str, ...]
    build: AssemblyBuildResult
    error: str


@dataclass(frozen=True)
class _PartUpdate:
    """One part of an edit: its id, its file and the text it gets."""

    part_id: str
    relative_path: str
    text: str


def apply_assembly_edit(
    project_root: Path,
    assembly_path: Path,
    part_updates: Mapping[str, str],
    runner: Runner,
    *,
    timeout_s: int = 60,  # starting default
) -> AssemblyEditResult:
    """Apply a change to the parts of an assembly and promote it when it verifies.

    ``part_updates`` maps a part id to the new source text of that part. The
    change is built and verified in a staging copy of the project, and the
    live project is written only when the whole assembly verifies.

    Raises ``AssemblyError`` when the change is empty, when a part id is not a
    plain name, when the project holds no file for a part, or when the
    assembly file lies outside the project.
    """
    project_root = Path(project_root).resolve()
    updates = _checked_updates(project_root, part_updates)
    manifest_path = _resolve_manifest(project_root, assembly_path)
    with tempfile.TemporaryDirectory(prefix="aturb-assembly-") as staging:
        staging_root = Path(staging) / "project"
        shutil.copytree(project_root, staging_root)
        _write_updates(staging_root, updates)
        staged_manifest = staging_root / \
            manifest_path.relative_to(project_root)
        try:
            staged = build_assembly(
                staging_root, staged_manifest, runner, timeout_s=timeout_s)
        except AssemblyError as exc:
            return _failed_edit("", str(exc))
        if staged.status != "ok":
            return AssemblyEditResult(
                status="failed", promoted=False, assembly_id=staged.assembly_id,
                updated_parts=(), build=staged, error=staged.error)
        originals = _read_originals(project_root, updates)
        _promote(project_root, updates)
        committed = build_assembly(
            project_root, manifest_path, runner, timeout_s=timeout_s)
        if committed.status != "ok":
            _restore(project_root, originals)
            return AssemblyEditResult(
                status="failed", promoted=False, assembly_id=committed.assembly_id,
                updated_parts=(), build=committed, error=committed.error)
        return AssemblyEditResult(
            status="ok", promoted=True, assembly_id=committed.assembly_id,
            updated_parts=tuple(update.part_id for update in updates),
            build=committed, error="")


def _resolve_manifest(project_root: Path, assembly_path: Path) -> Path:
    """Return the manifest of the assembly, refused when it leaves the project."""
    try:
        return resolve_inside(project_root, assembly_path)
    except PathEscapeError as exc:
        raise AssemblyError(
            f"the assembly file lies outside the project: {exc}") from exc


def _checked_updates(project_root: Path,
                     part_updates: Mapping[str, str]) -> tuple[_PartUpdate, ...]:
    """Return the file of every updated part, relative to the project root.

    The file of every part is resolved inside the parts folder of the project,
    so a change can never reach a file outside it.
    """
    if not isinstance(part_updates, Mapping) or not part_updates:
        raise AssemblyError("the edit holds no part to update")
    parts_dir = resolve_inside(project_root, PARTS_DIR)
    updates: list[_PartUpdate] = []
    for part_id, text in part_updates.items():
        if not isinstance(part_id, str) or not PART_ID_RE.fullmatch(part_id):
            raise AssemblyError(f"the part id {part_id!r} is not a plain name")
        if not isinstance(text, str):
            raise AssemblyError(
                f"the new source of the part {part_id!r} is not text")
        target = _part_file(parts_dir, part_id)
        updates.append(_PartUpdate(
            part_id=part_id, relative_path=to_rel(project_root, target), text=text))
    return tuple(updates)


def _part_file(parts_dir: Path, part_id: str) -> Path:
    """Return the file of one part inside the parts folder."""
    matches = sorted(path for path in parts_dir.glob(
        f"{part_id}_*") if path.is_file())
    matches += sorted(path for path in parts_dir.glob(
        f"{part_id}.*") if path.is_file())
    if not matches:
        raise AssemblyError(f"the project holds no part file for {part_id!r}")
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise AssemblyError(f"the part id {part_id!r} is ambiguous: {names}")
    return resolve_inside(parts_dir, matches[0].name)


def _write_updates(root: Path, updates: tuple[_PartUpdate, ...]) -> None:
    """Write the new source of every updated part into a project."""
    for update in updates:
        target = resolve_inside(root, update.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(update.text, encoding="utf-8")


def _promote(project_root: Path, updates: tuple[_PartUpdate, ...]) -> None:
    """Write the new source of every updated part into the live project."""
    for update in updates:
        _atomic_write(resolve_inside(
            project_root, update.relative_path), update.text)


def _read_originals(project_root: Path,
                    updates: tuple[_PartUpdate, ...]) -> dict[str, str]:
    """Return the source of every updated part, as it is now."""
    originals: dict[str, str] = {}
    for update in updates:
        target = resolve_inside(project_root, update.relative_path)
        originals[update.relative_path] = target.read_text(encoding="utf-8")
    return originals


def _restore(project_root: Path, originals: Mapping[str, str]) -> None:
    """Put the source of every updated part back as it was."""
    for relative, text in originals.items():
        _atomic_write(resolve_inside(project_root, relative), text)


def _atomic_write(path: Path, text: str) -> None:
    """Write a text to a file atomically, through the shared helper."""
    atomic_write_text(path, text)


def _failed_edit(assembly_id: str, error: str) -> AssemblyEditResult:
    """Return a failed edit that never reached the build."""
    build = AssemblyBuildResult(
        status="failed", assembly_id=assembly_id, assembly_name="",
        part_results={}, assembly_step="", manifest_path="", report=None,
        error=error)
    return AssemblyEditResult(
        status="failed", promoted=False, assembly_id=assembly_id,
        updated_parts=(), build=build, error=error)
