"""Offline tests for the assembly build and the safe assembly edit.

The stub pack builds every part by copying a packaged fixture STEP, so the
whole pipeline runs without a CAD. The fixture is a 120 x 60 x 5 mm plate
centred on the origin, so a component placed 6 mm above another one leaves a
1 mm gap.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from aturb.assembly.build import build_assembly
from aturb.assembly.edit import apply_assembly_edit
from aturb.packs import default_packs_root, load_runner

TOL = 0.01  # starting default
PART_TEXT = "# stub part\n"
BROKEN_TEXT = "# STUB: fail=syntax_error\n"

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


def _project(tmp_path: Path, top: tuple[float, float, float] = (0.0, 0.0, 6.0),
             part_text: str = PART_TEXT) -> Path:
    """Write a project with two stub parts and one assembly manifest."""
    project = tmp_path / "project"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001_base_plate.stub").write_text(part_text, encoding="utf-8")
    (parts / "plt0002_top_plate.stub").write_text(part_text, encoding="utf-8")
    assemblies = project / "assemblies"
    assemblies.mkdir(parents=True)
    manifest = MANIFEST.replace(
        "position = [0.0, 0.0, 6.0]", f"position = [{top[0]}, {top[1]}, {top[2]}]")
    (assemblies / "asm0001.toml").write_text(manifest, encoding="utf-8")
    return project


def _manifest_path(project: Path) -> Path:
    """Return the manifest of the assembly of a project."""
    return project / "assemblies" / "asm0001.toml"


def _result_path(project: Path) -> Path:
    """Return the result file of the assembly of a project."""
    return project / "out" / "assemblies" / "asm0001" / "assembly_result.toml"


def _step_path(project: Path) -> Path:
    """Return the compound STEP file of the assembly of a project."""
    return project / "out" / "assemblies" / "asm0001" / "asm0001.step"


def test_a_clean_assembly_builds_and_writes_a_portable_result(tmp_path):
    """Two components with a 1 mm gap build and verify as one assembly."""
    project = _project(tmp_path)

    result = build_assembly(project, _manifest_path(project), _runner())

    assert result.status == "ok"
    assert result.assembly_id == "asm0001"
    assert result.assembly_name == "Two plates"
    assert result.error == ""
    assert result.report is not None
    assert result.report.component_count == 2
    assert not result.report.has_interference
    assert result.report.all_mates_ok
    assert abs(result.report.pairs[0].min_clearance_mm - 1.0) <= TOL
    assert _step_path(project).is_file()
    assert result.assembly_step == "out/assemblies/asm0001/asm0001.step"
    assert result.manifest_path == "out/assemblies/asm0001/assembly_result.toml"


def test_the_result_file_holds_no_host_path(tmp_path):
    """The result file is portable: it names no path of the host."""
    project = _project(tmp_path)

    build_assembly(project, _manifest_path(project), _runner())

    text = _result_path(project).read_text(encoding="utf-8")
    assert str(project) not in text
    assert ":\\" not in text
    data = tomllib.loads(text)
    assert data["status"] == "ok"
    assert data["assembly_id"] == "asm0001"
    assert data["step_file"] == "asm0001.step"
    assert data["component_count"] == 2
    assert data["has_interference"] is False
    assert data["all_mates_ok"] is True
    assert len(data["pairs"]) == 1
    assert data["pairs"][0]["part_a"] == "plate"
    assert data["pairs"][0]["part_b"] == "plate_top"


def test_a_clashing_assembly_fails(tmp_path):
    """Two components on the same spot share material and fail."""
    project = _project(tmp_path, top=(0.0, 0.0, 0.0))

    result = build_assembly(project, _manifest_path(project), _runner())

    assert result.status == "failed"
    assert result.report is not None
    assert result.report.has_interference
    assert "interfere" in result.error
    data = tomllib.loads(_result_path(project).read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["has_interference"] is True


def test_a_failing_part_leaves_no_compound_step(tmp_path):
    """A part that fails to build never leaves a compound STEP behind."""
    project = _project(tmp_path)
    first = build_assembly(project, _manifest_path(project), _runner())
    assert first.status == "ok"
    assert _step_path(project).is_file()

    (project / "parts" / "plt0002_top_plate.stub").write_text(
        BROKEN_TEXT, encoding="utf-8")
    second = build_assembly(project, _manifest_path(project), _runner())

    assert second.status == "failed"
    assert second.report is None
    assert "plt0002" in second.error
    assert not _step_path(project).exists()
    data = tomllib.loads(_result_path(project).read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["step_file"] == ""


def test_a_rejected_edit_leaves_the_project_byte_for_byte_untouched(tmp_path):
    """An edit that does not verify changes nothing in the live project."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    part = project / "parts" / "plt0002_top_plate.stub"
    before_part = part.read_bytes()
    before_result = _result_path(project).read_bytes()
    before_step = _step_path(project).read_bytes()

    edit = apply_assembly_edit(
        project, _manifest_path(project), {"plt0002": BROKEN_TEXT}, _runner())

    assert edit.status == "failed"
    assert edit.promoted is False
    assert edit.updated_parts == ()
    assert edit.build.status == "failed"
    assert part.read_bytes() == before_part
    assert _result_path(project).read_bytes() == before_result
    assert _step_path(project).read_bytes() == before_step


def test_a_valid_edit_is_promoted(tmp_path):
    """An edit that verifies is written into the live project."""
    project = _project(tmp_path)
    build_assembly(project, _manifest_path(project), _runner())
    part = project / "parts" / "plt0002_top_plate.stub"

    edit = apply_assembly_edit(
        project, _manifest_path(project), {"plt0002": "# updated part\n"}, _runner())

    assert edit.status == "ok"
    assert edit.promoted is True
    assert edit.updated_parts == ("plt0002",)
    assert edit.build.status == "ok"
    assert part.read_text(encoding="utf-8") == "# updated part\n"
    assert _step_path(project).is_file()
    data = tomllib.loads(_result_path(project).read_text(encoding="utf-8"))
    assert data["status"] == "ok"


def test_an_empty_edit_is_refused(tmp_path):
    """An edit that changes nothing is refused before it starts."""
    project = _project(tmp_path)

    try:
        apply_assembly_edit(
            project, _manifest_path(project), {}, _runner())
    except ValueError as exc:
        assert "no part" in str(exc)
    else:
        raise AssertionError("an empty edit must be refused")
