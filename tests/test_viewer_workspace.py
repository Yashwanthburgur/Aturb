"""Tests for the safe workspace loader of the viewer client."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from aturb.agent.generate import GenerateResult
from aturb.agent.generate_cli import write_generate_manifest
from clients.viewer.workspace import (
    DECLARED_ARTIFACT_KINDS,
    ArtifactMissingError,
    WorkspaceError,
    load_workspace,
    resolve_artifact,
    resolve_workspace_path,
)

NO_ARTIFACTS = {"part_file": None, "step_file": None, "native_file": None}


def _write_workspace(root: Path) -> Path:
    """Write a workspace with three artifacts and its manifest."""
    project = root / "project"
    (project / "parts").mkdir(parents=True, exist_ok=True)
    (project / "out").mkdir(parents=True, exist_ok=True)
    part = project / "parts" / "part0001.py"
    step = project / "out" / "part0001.step"
    native = project / "out" / "part0001.native"
    part.write_text("# candidate\n", encoding="utf-8")
    step.write_text("ISO-10303-21;\n", encoding="utf-8")
    native.write_bytes(b"native")
    result = GenerateResult(
        status="ok",
        part_id="part0001",
        workspace=root,
        part_path=part,
        step_path=step,
        native_path=native,
        build_status="ok",
        attempts=1,
        input_tokens=120,
        output_tokens=45,
        cost_usd=0.001,
        prompt_version="v1",
        stop_reason="built",
    )
    return write_generate_manifest(result)


def _write_manifest(root: Path, text: str) -> Path:
    """Write a manifest by hand and return its path."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / "result.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_written_workspace_loads_with_its_three_artifacts(tmp_path: Path):
    """A workspace written by the generator loads with its manifest and paths."""
    root = tmp_path / "workspace"
    manifest_path = _write_workspace(root)

    workspace = load_workspace(root)

    assert workspace.root == root.resolve()
    with manifest_path.open("rb") as handle:
        assert workspace.manifest == tomllib.load(handle)
    assert workspace.manifest["status"] == "ok"
    assert workspace.manifest["stop_reason"] == "built"
    assert workspace.manifest["attempts"] == 1
    assert set(workspace.artifacts) == set(DECLARED_ARTIFACT_KINDS)
    for kind in DECLARED_ARTIFACT_KINDS:
        artifact = workspace.artifacts[kind]
        assert artifact is not None
        assert artifact.is_relative_to(workspace.root)
        assert artifact.is_file()
        assert resolve_artifact(workspace, kind) == artifact


def test_a_failed_manifest_with_empty_artifacts_loads_cleanly(tmp_path: Path):
    """A manifest of a failed generation loads with no artifact and all fields."""
    root = tmp_path / "failed"
    _write_manifest(root, (
        'status = "error"\n'
        'part_id = "part0001"\n'
        'stop_reason = "build_failed"\n'
        'attempts = 2\n'
        'build_status = "failed"\n'
        'failure_kind = "syntax_error"\n'
        'error = "the candidate did not compile"\n'
        'conventions = ["a finding"]\n'
        'part_file = ""\n'
        'step_file = ""\n'
        'native_file = ""\n'
    ))

    workspace = load_workspace(root)

    assert workspace.artifacts == NO_ARTIFACTS
    assert workspace.manifest["status"] == "error"
    assert workspace.manifest["stop_reason"] == "build_failed"
    assert workspace.manifest["build_status"] == "failed"
    assert workspace.manifest["failure_kind"] == "syntax_error"
    assert workspace.manifest["error"] == "the candidate did not compile"
    assert workspace.manifest["conventions"] == ["a finding"]
    for kind in DECLARED_ARTIFACT_KINDS:
        with pytest.raises(ArtifactMissingError):
            resolve_artifact(workspace, kind)


def test_a_manifest_without_artifact_keys_loads_cleanly(tmp_path: Path):
    """A manifest that names no artifact at all loads with no artifact."""
    root = tmp_path / "absent"
    _write_manifest(root, (
        'status = "error"\n'
        'part_id = "part0001"\n'
        'stop_reason = "preparation_error"\n'
        'error = "the requirement was empty"\n'
    ))

    workspace = load_workspace(root)

    assert workspace.artifacts == NO_ARTIFACTS
    assert workspace.manifest["status"] == "error"
    assert workspace.manifest["error"] == "the requirement was empty"
    with pytest.raises(ArtifactMissingError):
        resolve_artifact(workspace, "step_file")


def test_a_missing_workspace_directory_is_refused(tmp_path: Path):
    """A workspace directory that is not there is refused."""
    with pytest.raises(WorkspaceError):
        load_workspace(tmp_path / "nowhere")


def test_a_missing_manifest_is_refused(tmp_path: Path):
    """A workspace without a result.toml is refused."""
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(WorkspaceError):
        load_workspace(root)


def test_a_malformed_manifest_is_refused(tmp_path: Path):
    """A manifest that is not valid TOML is refused."""
    root = tmp_path / "broken"
    _write_manifest(root, 'status = "unclosed\n')
    with pytest.raises(WorkspaceError):
        load_workspace(root)


@pytest.mark.parametrize("declared", ["../outside.step", "project/../../escape.step"])
def test_a_traversal_path_is_refused(tmp_path: Path, declared: str):
    """A declared path that walks out of the workspace is refused."""
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(WorkspaceError):
        resolve_workspace_path(root, declared)


def test_a_traversal_path_in_a_manifest_is_refused(tmp_path: Path):
    """A manifest that declares a path out of the workspace is refused."""
    root = tmp_path / "workspace"
    _write_manifest(root, 'status = "ok"\nstep_file = "../outside.step"\n')
    with pytest.raises(WorkspaceError):
        load_workspace(root)


@pytest.mark.parametrize(
    "declared",
    ["C:\\Windows\\win.ini", "C:/temp/a.step", "/etc/passwd"])
def test_an_absolute_path_is_refused(tmp_path: Path, declared: str):
    """A declared absolute path is refused."""
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(WorkspaceError):
        resolve_workspace_path(root, declared)


def test_an_empty_declared_path_is_refused(tmp_path: Path):
    """A declared empty path is refused."""
    root = tmp_path / "workspace"
    root.mkdir()
    with pytest.raises(WorkspaceError):
        resolve_workspace_path(root, "")


def test_an_escaping_symlink_is_refused(tmp_path: Path):
    """A symbolic link that leaves the workspace is refused."""
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.step"
    outside.write_text("not a step", encoding="utf-8")
    link = root / "link.step"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow symbolic links")
    with pytest.raises(WorkspaceError):
        resolve_workspace_path(root, "link.step")


def test_an_escaping_symlink_is_refused_without_a_symlink(
        tmp_path: Path, monkeypatch):
    """The containment check refuses a path that resolves outside the root."""
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.step"
    outside.write_text("not a step", encoding="utf-8")
    real_resolve = Path.resolve

    def fake_resolve(self, strict=False):
        if self.name == "link.step":
            return outside.resolve()
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    with pytest.raises(WorkspaceError):
        resolve_workspace_path(root, "link.step")


@pytest.mark.parametrize("kind", ["result.toml", "../secret"])
def test_an_unknown_artifact_kind_is_refused(tmp_path: Path, kind: str):
    """A kind that the manifest does not declare is refused."""
    root = tmp_path / "workspace"
    _write_manifest(root, 'status = "ok"\n')
    workspace = load_workspace(root)
    with pytest.raises(WorkspaceError) as info:
        resolve_artifact(workspace, kind)
    assert not isinstance(info.value, ArtifactMissingError)


def test_a_declared_artifact_that_is_not_there_is_missing(tmp_path: Path):
    """A declared artifact that is not on disk is missing, not refused."""
    root = tmp_path / "workspace"
    _write_manifest(
        root, 'status = "ok"\nstep_file = "project/out/gone.step"\n')
    workspace = load_workspace(root)
    assert workspace.artifacts["step_file"] is not None
    with pytest.raises(ArtifactMissingError):
        resolve_artifact(workspace, "step_file")
