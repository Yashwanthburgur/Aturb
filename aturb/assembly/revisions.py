"""The immutable revision history of one assembly.

Every assembly keeps its history in the output folder of the assembly:
`assembly_history.toml` names the active revision and every revision, and
`revisions/rNNNN/` holds an immutable snapshot of a verified state. A revision
is never rewritten, and the history is written atomically.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import tomllib
from collections.abc import Sequence
from pathlib import Path

from aturb.agent.record import toml_string
from aturb.assembly.edit import _part_file
from aturb.assembly.manifest import AssemblyError, AssemblySpec, load_assembly
from aturb.assembly.prompt import _part_ids
from aturb.workspace.paths import PathEscapeError, resolve_inside, to_rel

HISTORY_FILE_NAME = "assembly_history.toml"
REVISIONS_DIR_NAME = "revisions"
PARTS_DIR_NAME = "parts"
RESULT_FILE_NAME = "assembly_result.toml"
OUT_DIR = "out"
ASSEMBLY_DIR = "assemblies"
INITIAL_REVISION_ID = "r0001"  # starting default
REVISION_ID_WIDTH = 4  # starting default
REVISION_ID_RE = re.compile(r"^r[0-9]{4,}$")
KINDS = ("initial", "edit")
STATUSES = ("ok", "failed")


def assembly_out_dir(project_root: Path, assembly_id: str) -> Path:
    """Return the output folder of the assembly inside the project."""
    try:
        return resolve_inside(
            project_root, f"{OUT_DIR}/{ASSEMBLY_DIR}/{assembly_id}")
    except PathEscapeError as exc:
        raise AssemblyError(
            f"the assembly id {assembly_id!r} leaves the project") from exc


def load_assembly_history(out_dir: Path) -> dict | None:
    """Read the history of an assembly, or None when it has none."""
    path = Path(out_dir) / HISTORY_FILE_NAME
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AssemblyError(
            f"the history of the assembly is unreadable: {exc}") from exc


def ensure_assembly_history(project_root: Path, assembly_path: Path,
                            spec: AssemblySpec) -> dict:
    """Return the history of the assembly, bootstrapping it when it has none.

    The first revision is the verified baseline: the part sources of the
    project and the verified outputs of the assembly are copied into it, so a
    rollback always finds a verified state to restore.
    """
    project_root = Path(project_root).resolve()
    out_dir = assembly_out_dir(project_root, spec.assembly_id)
    history = load_assembly_history(out_dir)
    if history is not None:
        return history
    _snapshot(project_root, out_dir, spec, INITIAL_REVISION_ID)
    entry = {
        "id": INITIAL_REVISION_ID,
        "parent": "",
        "kind": "initial",
        "status": "ok",
        "stop_reason": "",
        "instruction": "",
        "attempts": 0,
        "updated_parts": [],
    }
    history = {
        "assembly_id": spec.assembly_id,
        "assembly_file": _assembly_file(project_root, assembly_path),
        "active_revision": INITIAL_REVISION_ID,
        "revisions": [entry],
    }
    _write_history(out_dir, history)
    return history


def record_assembly_revision(project_root: Path, assembly_path: Path,
                             spec: AssemblySpec, *, kind: str, status: str,
                             stop_reason: str, instruction: str, attempts: int,
                             updated_parts: Sequence[str],
                             promote: bool) -> dict:
    """Record one revision of the assembly and return its entry.

    A promoted revision snapshots the verified state of the assembly and
    becomes the active one. A failed revision records its metadata only: it
    never overwrites the active outputs of the assembly.
    """
    project_root = Path(project_root).resolve()
    out_dir = assembly_out_dir(project_root, spec.assembly_id)
    history = load_assembly_history(out_dir)
    if history is None:
        history = ensure_assembly_history(project_root, assembly_path, spec)
    revision_id = _next_revision_id(history)
    entry = {
        "id": revision_id,
        "parent": str(history.get("active_revision", "")),
        "kind": kind,
        "status": status,
        "stop_reason": stop_reason,
        "instruction": instruction,
        "attempts": int(attempts),
        "updated_parts": list(updated_parts),
    }
    if promote:
        _snapshot(project_root, out_dir, spec, revision_id)
        history["active_revision"] = revision_id
    history["revisions"] = list(history.get("revisions", [])) + [entry]
    _write_history(out_dir, history)
    return entry


def rollback_assembly(project_root: Path, assembly_path: Path,
                      revision_id: str) -> dict:
    """Restore a verified revision of the assembly and return the history.

    The part sources and the verified outputs of the revision are copied back
    into the live project, one file at a time and atomically, and the revision
    becomes the active one.
    """
    project_root = Path(project_root).resolve()
    spec = load_assembly(resolve_inside(project_root, assembly_path))
    out_dir = assembly_out_dir(project_root, spec.assembly_id)
    history = load_assembly_history(out_dir)
    if history is None:
        raise AssemblyError("the assembly has no revision history")
    entry = _find(history, revision_id)
    if entry.get("status") != "ok":
        raise AssemblyError(
            f"the revision {revision_id!r} is not a verified revision")
    revision_dir = resolve_inside(
        out_dir, f"{REVISIONS_DIR_NAME}/{revision_id}")
    _restore(project_root, out_dir, revision_dir, spec)
    history["active_revision"] = revision_id
    _write_history(out_dir, history)
    return history


def _assembly_file(project_root: Path, assembly_path: Path) -> str:
    """Return the manifest of the assembly, relative to the project root."""
    return to_rel(project_root, resolve_inside(project_root, assembly_path))


def _snapshot(project_root: Path, out_dir: Path, spec: AssemblySpec,
              revision_id: str) -> None:
    """Copy the verified state of the assembly into a revision folder."""
    revision_dir = out_dir / REVISIONS_DIR_NAME / revision_id
    if revision_dir.exists():
        shutil.rmtree(revision_dir)
    parts_dir = revision_dir / PARTS_DIR_NAME
    parts_dir.mkdir(parents=True)
    live_parts = resolve_inside(project_root, PARTS_DIR_NAME)
    for part_id in _part_ids(spec):
        source = _part_file(live_parts, part_id)
        shutil.copy2(source, parts_dir / source.name)
    for name in (RESULT_FILE_NAME, f"{spec.assembly_id}.step"):
        source = out_dir / name
        if source.is_file():
            shutil.copy2(source, revision_dir / name)


def _restore(project_root: Path, out_dir: Path, revision_dir: Path,
             spec: AssemblySpec) -> None:
    """Copy the snapshot of a revision back into the live project."""
    parts_dir = revision_dir / PARTS_DIR_NAME
    if parts_dir.is_dir():
        live_parts = resolve_inside(project_root, PARTS_DIR_NAME)
        for source in sorted(parts_dir.iterdir()):
            if source.is_file():
                _atomic_copy(source, resolve_inside(live_parts, source.name))
    for name in (RESULT_FILE_NAME, f"{spec.assembly_id}.step"):
        source = revision_dir / name
        if source.is_file():
            _atomic_copy(source, out_dir / name)


def _find(history: dict, revision_id: str) -> dict:
    """Return one recorded revision, or raise when it is not recorded."""
    for entry in history.get("revisions", []):
        if str(entry.get("id", "")) == revision_id:
            return entry
    raise AssemblyError(f"the revision {revision_id!r} is not in the history")


def _next_revision_id(history: dict) -> str:
    """Return the next free revision id of a history."""
    highest = 0
    for entry in history.get("revisions", []):
        revision_id = str(entry.get("id", ""))
        if REVISION_ID_RE.fullmatch(revision_id):
            highest = max(highest, int(revision_id[1:]))
    return f"r{highest + 1:0{REVISION_ID_WIDTH}d}"


def _write_history(out_dir: Path, history: dict) -> Path:
    """Write the history of an assembly atomically and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"assembly_id = {toml_string(str(history.get('assembly_id', '')))}",
        f"assembly_file = {toml_string(str(history.get('assembly_file', '')))}",
        f"active_revision = {toml_string(str(history.get('active_revision', '')))}",
        "",
    ]
    for entry in history.get("revisions", []):
        lines.append("[[revisions]]")
        lines.append(f"id = {toml_string(str(entry.get('id', '')))}")
        lines.append(f"parent = {toml_string(str(entry.get('parent', '')))}")
        lines.append(f"kind = {toml_string(str(entry.get('kind', '')))}")
        lines.append(f"status = {toml_string(str(entry.get('status', '')))}")
        lines.append(
            f"stop_reason = {toml_string(str(entry.get('stop_reason', '')))}")
        lines.append(
            f"instruction = {toml_string(str(entry.get('instruction', '')))}")
        lines.append(f"attempts = {int(entry.get('attempts', 0))}")
        lines.append(
            f"updated_parts = {_strings(entry.get('updated_parts', []))}")
        lines.append("")
    path = out_dir / HISTORY_FILE_NAME
    _atomic_write(path, "\n".join(lines))
    return path


def _strings(items: object) -> str:
    """Return a list of texts as a TOML array."""
    if not isinstance(items, (list, tuple)):
        return "[]"
    return "[" + ", ".join(toml_string(str(item)) for item in items) + "]"


def _atomic_write(path: Path, data: str | bytes) -> None:
    """Write data to a file through a temporary file in the same folder."""
    payload = data.encode("utf-8") if isinstance(data, str) else data
    handle, name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _atomic_copy(source: Path, target: Path) -> None:
    """Copy a file into place through a temporary file in the same folder."""
    target.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(target, source.read_bytes())
