"""Tests for the stub runner: success path and every scripted failure kind."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.contract.types import BuildRequest, FailureKind
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFORMANCE_STUB = REPO_ROOT / "tests" / "fixtures" / "conformance" / "stub"


def make_project(tmp_path: Path, part_text: str = "stub part file") -> Path:
    """Create a tmp project with one stub part and return its root."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts / "plt0001_base_plate.stub").write_text(part_text, encoding="utf-8")
    return project


def make_runner():
    """Load the stub runner with empty settings."""
    return load_runner("stub", {"packs": {}}, default_packs_root())


def request(project: Path, part_id: str = "plt0001",
            language: str = "stub-text") -> BuildRequest:
    """Build a request for one part of a tmp project."""
    return BuildRequest(
        project_root=str(project), part_id=part_id, language=language)


def test_ok_build_returns_both_artifacts(tmp_path):
    """A good stub part builds and both artifacts exist."""
    project = make_project(tmp_path)

    result = make_runner().build(request(project))

    assert result.status == "ok"
    for key in ("native", "step"):
        assert key in result.artifacts
        assert (project / result.artifacts[key]).is_file()


def test_wrong_language_is_input_error(tmp_path):
    """A request in the wrong language fails with INPUT_ERROR."""
    project = make_project(tmp_path)

    result = make_runner().build(request(project, language="python"))

    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR


def test_missing_part_is_input_error(tmp_path):
    """An unknown part id fails with INPUT_ERROR."""
    project = make_project(tmp_path)

    result = make_runner().build(request(project, part_id="zzz9999"))

    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR


def test_ambiguous_part_is_input_error(tmp_path):
    """Two matching part files fail with INPUT_ERROR."""
    project = make_project(tmp_path)
    shutil.copyfile(
        project / "parts" / "plt0001_base_plate.stub",
        project / "parts" / "plt0001_other.stub",
    )

    result = make_runner().build(request(project))

    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR


def test_non_utf8_part_file_is_input_error(tmp_path):
    """A part file that is not UTF-8 text fails with INPUT_ERROR."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    (parts /
     "plt0001_base_plate.stub").write_bytes(bytes([255, 254]) + b" bad\n")

    result = make_runner().build(request(project))

    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR
    assert "UTF-8" in result.error_text


def test_fixture_is_a_package_resource():
    """The STEP fixture is shipped inside the stub package."""
    from importlib.resources import files

    resource = files("packs.stub").joinpath("fixtures/plate_2holes.step")
    assert resource.is_file()
    assert resource.read_bytes().startswith(b"ISO-10303-21")


def test_empty_part_file_is_input_error(tmp_path):
    """An empty part file fails with INPUT_ERROR instead of raising."""
    project = make_project(tmp_path, part_text="")

    result = make_runner().build(request(project))

    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR
    assert "empty" in result.error_text


@pytest.mark.parametrize("kind", [
    k.value for k in FailureKind if k is not FailureKind.INPUT_ERROR
])
def test_scripted_failure(tmp_path, kind):
    """A '# STUB: fail=<kind>' first line returns that failure kind."""
    project = make_project(tmp_path, part_text=f"# STUB: fail={kind}")

    result = make_runner().build(request(project))

    assert result.status == "failed"
    assert result.failure_kind is FailureKind(kind)
    assert result.artifacts == {}
