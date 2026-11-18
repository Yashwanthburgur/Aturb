"""End-to-end FreeCAD tests: every failure kind reachable through the real runner."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest, FailureKind
from aturb.packs import default_packs_root, load_runner

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANTED = Path(__file__).resolve().parent / "fc_planted"

CASES = [
    ("syntax_err.py", FailureKind.SYNTAX_ERROR, 60),
    ("runtime_err.py", FailureKind.RUNTIME_ERROR, 60),
    ("infinite_loop.py", FailureKind.TIMEOUT, 5),
    ("invalid_geom.py", FailureKind.INVALID_GEOMETRY, 60),
    ("unsafe_import.py", FailureKind.REJECTED_UNSAFE, 60),
    ("export_fail.py", FailureKind.EXPORT_FAILED, 60),
]


def make_runner():
    """Load the real FreeCAD runner with the local config."""
    cfg = load_config(REPO_ROOT / "aturb.local.toml")
    return load_runner("freecad", cfg, default_packs_root())


@pytest.mark.freecad
@pytest.mark.parametrize("filename,kind,timeout_s", CASES,
                         ids=[c[0] for c in CASES])
def test_planted_failure(tmp_path, filename, kind, timeout_s):
    """Each planted part produces its expected failure kind."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    shutil.copyfile(PLANTED / filename, parts / "zzz0001_planted.py")

    request = BuildRequest(
        project_root=str(project),
        part_id="zzz0001",
        language="python-freecad",
        timeout_s=timeout_s,
    )
    result = make_runner().build(request)

    assert result.status == "failed"
    assert result.failure_kind is kind
    assert result.artifacts == {}


@pytest.mark.freecad
def test_invalid_geometry_names_only_the_failed_feature(tmp_path):
    """Only the feature with the Invalid flag is named, not its container."""
    project = tmp_path / "proj"
    parts = project / "parts"
    parts.mkdir(parents=True)
    shutil.copyfile(PLANTED / "invalid_geom.py", parts / "zzz0001_planted.py")

    request = BuildRequest(
        project_root=str(project),
        part_id="zzz0001",
        language="python-freecad",
        timeout_s=60,
    )
    result = make_runner().build(request)

    assert result.failure_kind is FailureKind.INVALID_GEOMETRY
    failed = result.native_diagnostics["failed_features"]
    assert failed == ["Pad"]
