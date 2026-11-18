"""Non-FreeCAD tests for the FreeCAD runner: loading, part resolution, precheck."""

from __future__ import annotations

from pathlib import Path

from aturb.contract.types import BuildRequest, FailureKind
from aturb.packs import default_packs_root, load_runner
from packs.freecad.runner import (
    clear_out_dir,
    convert_artifacts,
    find_part_file,
    parse_result,
)


def make_runner():
    """Load the FreeCAD runner with a deliberately invalid cmd."""
    return load_runner(
        "freecad",
        {"packs": {"freecad": {"cmd": "does-not-exist"}}},
        default_packs_root(),
    )


def make_project(tmp_path: Path, part_text: str) -> Path:
    """Create a tmp project with one part file and return its root."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001_base_plate.py").write_text(part_text, encoding="utf-8")
    return project


def test_runner_loads_without_cad():
    """load_runner returns a runner whose info().name is freecad."""
    runner = make_runner()
    assert runner.info().name == "freecad"


def test_find_part_file_one_match(tmp_path):
    """Exactly one matching part file is returned."""
    project = make_project(tmp_path, "def build(doc):\n    return None\n")
    part = find_part_file(project, "plt0001")
    assert isinstance(part, Path)
    assert part.name == "plt0001_base_plate.py"


def test_find_part_file_no_match(tmp_path):
    """No matching part file returns an error string."""
    project = make_project(tmp_path, "def build(doc):\n    return None\n")
    assert find_part_file(project, "zzz9999") == "no part file for zzz9999"


def test_find_part_file_ambiguous(tmp_path):
    """Two matching part files return an ambiguity string."""
    project = make_project(tmp_path, "def build(doc):\n    return None\n")
    (project / "parts" / "plt0001_other.py").write_text(
        "def build(doc):\n    return None\n", encoding="utf-8")
    result = find_part_file(project, "plt0001")
    assert isinstance(result, str)
    assert "ambiguous" in result


def test_unsafe_part_rejected_before_launch(tmp_path):
    """A part with 'import os' fails REJECTED_UNSAFE without launching the CAD."""
    project = make_project(tmp_path, "import os\n")
    request = BuildRequest(
        project_root=str(project), part_id="plt0001", language="python-freecad")
    result = make_runner().build(request)
    assert result.status == "failed"
    assert result.failure_kind is FailureKind.REJECTED_UNSAFE


def test_convert_artifacts_inside(tmp_path):
    """An artifact inside the project converts to a relative path."""
    project = tmp_path / "proj"
    project.mkdir()
    converted = convert_artifacts(
        project, {"step": str(project / "out" / "a.step")})
    assert converted == {"step": "out/a.step"}


def test_convert_artifacts_outside(tmp_path):
    """An artifact outside the project returns an error string."""
    project = tmp_path / "proj"
    project.mkdir()
    result = convert_artifacts(
        project, {"step": str(tmp_path / "elsewhere.step")})
    assert isinstance(result, str)
    assert "step" in result


def test_non_utf8_part_file_is_input_error(tmp_path):
    """A part file that is not UTF-8 text fails with INPUT_ERROR."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts /
     "plt0001_base_plate.py").write_bytes(bytes([255, 254]) + b" bad\n")
    request = BuildRequest(
        project_root=str(project), part_id="plt0001", language="python-freecad")
    result = make_runner().build(request)
    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR
    assert "UTF-8" in result.error_text


def test_missing_cad_executable_is_runner_crash(tmp_path):
    """A CAD command that cannot start returns RUNNER_CRASH, not an exception."""
    project = make_project(tmp_path, "def build(doc):\n    return None\n")
    request = BuildRequest(
        project_root=str(project), part_id="plt0001", language="python-freecad")
    result = make_runner().build(request)
    assert result.status == "failed"
    assert result.failure_kind is FailureKind.RUNNER_CRASH
    assert "cannot start the CAD process" in result.error_text


def test_parse_result_rejects_unknown_failure_kind(tmp_path):
    """An unknown failure_kind is reported as a malformed result."""
    project = tmp_path / "proj"
    project.mkdir()
    raw = {"status": "failed", "failure_kind": "not_a_kind", "error_text": "x"}
    result = parse_result(raw, project)
    assert isinstance(result, str)
    assert "unknown failure_kind" in result


def test_parse_result_rejects_unknown_status(tmp_path):
    """An unknown status is reported as a malformed result."""
    project = tmp_path / "proj"
    project.mkdir()
    result = parse_result({"status": "maybe"}, project)
    assert isinstance(result, str)
    assert "unknown status" in result


def test_parse_result_rejects_non_object(tmp_path):
    """A result that is not a JSON object is reported as malformed."""
    project = tmp_path / "proj"
    project.mkdir()
    result = parse_result(["not", "a", "dict"], project)
    assert isinstance(result, str)
    assert "expected a JSON object" in result


def test_parse_result_accepts_a_good_result(tmp_path):
    """A well formed result is converted into BuildResult fields."""
    project = tmp_path / "proj"
    project.mkdir()
    raw = {
        "status": "ok",
        "failure_kind": None,
        "error_text": "",
        "artifacts": {"step": str(project / "out" / "a.step")},
        "native_diagnostics": {"cad_version": "1.0"},
    }
    parsed = parse_result(raw, project)
    assert parsed["status"] == "ok"
    assert parsed["failure_kind"] is None
    assert parsed["artifacts"] == {"step": "out/a.step"}


def test_clear_out_dir_removes_files_and_subfolders(tmp_path):
    """Cleanup removes stale files and subfolders inside the output folder."""
    out_dir = tmp_path / "out" / "plt0001"
    (out_dir / "sub").mkdir(parents=True)
    (out_dir / "sub" / "old.step").write_text("x", encoding="utf-8")
    (out_dir / "old.log").write_text("x", encoding="utf-8")

    clear_out_dir(out_dir)

    assert list(out_dir.iterdir()) == []
