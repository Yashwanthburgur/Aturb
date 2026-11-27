"""Offline tests for the revision history of an assembly.

The stub pack builds every part by copying a packaged fixture STEP, so the
whole history runs without a CAD. The history is immutable: a revision is
never rewritten, and a rollback always finds a verified state to restore.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from aturb.assembly.build import build_assembly
from aturb.assembly.manifest import AssemblyError, load_assembly
from aturb.assembly.revisions import (
    assembly_out_dir,
    ensure_assembly_history,
    load_assembly_history,
    record_assembly_revision,
    rollback_assembly,
)
from aturb.packs import default_packs_root, load_runner

PART_TEXT = "# stub part\n"
UPDATED_TEXT = "# updated stub part\n"

MANIFEST = """
assembly_id = "asm0001"
name = "Two plates"

[[components]]
name = "plate"
part_id = "plt0001"
position = [0.0, 0.0, 0.0]

[[components]]
name = "plate_top"
part_id = "plt0002"
position = [0.0, 0.0, 6.0]

[[mates]]
part_a = "plate"
part_b = "plate_top"
min_clearance_mm = 0.5
max_clearance_mm = 1.5
"""


def _runner():
    """Load the stub runner with empty settings."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def _project(tmp_path: Path) -> Path:
    """Write a project with two stub parts and one assembly manifest."""
    project = tmp_path / "project"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001_base_plate.stub").write_text(PART_TEXT, encoding="utf-8")
    (parts / "plt0002_top_plate.stub").write_text(PART_TEXT, encoding="utf-8")
    assemblies = project / "assemblies"
    assemblies.mkdir(parents=True)
    (assemblies / "asm0001.toml").write_text(MANIFEST, encoding="utf-8")
    return project


def _manifest_path(project: Path) -> Path:
    """Return the manifest of the assembly of a project."""
    return project / "assemblies" / "asm0001.toml"


def _out_dir(project: Path) -> Path:
    """Return the output folder of the assembly of a project."""
    return assembly_out_dir(project, "asm0001")


def _history_path(project: Path) -> Path:
    """Return the history file of the assembly of a project."""
    return _out_dir(project) / "assembly_history.toml"


def _spec(project: Path):
    """Return the specification of the assembly of a project."""
    return load_assembly(_manifest_path(project))


def _record(project: Path, *, status: str, promote: bool) -> dict:
    """Record one revision of the assembly of a project."""
    return record_assembly_revision(
        project, _manifest_path(project), _spec(project), kind="edit",
        status=status, stop_reason="built" if status == "ok" else "max_attempts",
        instruction="widen the pin", attempts=1,
        updated_parts=("plt0002",) if status == "ok" else (), promote=promote)


def test_an_assembly_without_a_history_has_none(tmp_path):
    """An assembly that was never edited has no history yet."""
    project = _project(tmp_path)

    assert load_assembly_history(_out_dir(project)) is None


def test_the_history_is_bootstrapped_with_the_verified_baseline(tmp_path):
    """The first revision is the verified state of the assembly."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())

    history = ensure_assembly_history(
        project, _manifest_path(project), _spec(project))

    assert history["assembly_id"] == "asm0001"
    assert history["active_revision"] == "r0001"
    entry = history["revisions"][0]
    assert entry["id"] == "r0001"
    assert entry["kind"] == "initial"
    assert entry["status"] == "ok"
    revision = _out_dir(project) / "revisions" / "r0001"
    assert (revision / "parts" / "plt0001_base_plate.stub").is_file()
    assert (revision / "assembly_result.toml").is_file()
    assert (revision / "asm0001.step").is_file()


def test_a_failed_revision_is_recorded_without_a_snapshot(tmp_path):
    """A revision that promoted nothing never becomes the active one."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))

    entry = _record(project, status="failed", promote=False)

    assert entry["id"] == "r0002"
    assert entry["parent"] == "r0001"
    assert entry["status"] == "failed"
    history = load_assembly_history(_out_dir(project))
    assert history["active_revision"] == "r0001"
    assert len(history["revisions"]) == 2
    assert not (_out_dir(project) / "revisions" / "r0002").exists()


def test_a_promoted_revision_becomes_the_active_one(tmp_path):
    """A verified revision snapshots the assembly and becomes active."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))
    part = project / "parts" / "plt0002_top_plate.stub"
    part.write_text(UPDATED_TEXT, encoding="utf-8")

    entry = _record(project, status="ok", promote=True)

    assert entry["id"] == "r0002"
    history = load_assembly_history(_out_dir(project))
    assert history["active_revision"] == "r0002"
    revision = _out_dir(project) / "revisions" / "r0002"
    assert (revision / "parts" / "plt0002_top_plate.stub").read_text(
        encoding="utf-8") == UPDATED_TEXT


def test_a_rollback_restores_the_parts_and_the_outputs(tmp_path):
    """A rollback brings back the parts and the outputs of a revision."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))
    part = project / "parts" / "plt0002_top_plate.stub"
    part.write_text(UPDATED_TEXT, encoding="utf-8")
    _record(project, status="ok", promote=True)

    history = rollback_assembly(project, _manifest_path(project), "r0001")

    assert history["active_revision"] == "r0001"
    assert part.read_text(encoding="utf-8") == PART_TEXT
    assert (_out_dir(project) / "assembly_result.toml").is_file()
    assert (_out_dir(project) / "asm0001.step").is_file()


def test_a_rollback_refuses_a_revision_that_did_not_verify(tmp_path):
    """Only a verified revision can be restored."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))
    _record(project, status="failed", promote=False)

    with pytest.raises(AssemblyError):
        rollback_assembly(project, _manifest_path(project), "r0002")


def test_a_rollback_refuses_a_revision_that_is_not_recorded(tmp_path):
    """A revision that was never recorded cannot be restored."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))

    with pytest.raises(AssemblyError):
        rollback_assembly(project, _manifest_path(project), "r0009")


def test_the_history_file_holds_no_host_path(tmp_path):
    """The history is portable: it names no path of the host."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))

    text = _history_path(project).read_text(encoding="utf-8")

    assert str(project) not in text
    assert ":\\" not in text
    data = tomllib.loads(text)
    assert data["assembly_file"] == "assemblies/asm0001.toml"
    assert data["active_revision"] == "r0001"


def test_the_history_leaves_no_temporary_file_behind(tmp_path):
    """Every write of the history goes through a temporary file."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    ensure_assembly_history(project, _manifest_path(project), _spec(project))
    _record(project, status="ok", promote=True)

    leftovers = [path.name for path in _out_dir(project).iterdir()
                 if path.name.endswith(".tmp")]

    assert leftovers == []
