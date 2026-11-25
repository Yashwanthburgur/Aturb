"""Tests for the neutral STEP tessellation of the viewer client."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import pytest

from aturb.config import load_config
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner
from clients.viewer.mesh import (
    DEFAULT_ANGULAR_TOLERANCE_RAD,
    DEFAULT_TOLERANCE_MM,
    MeshError,
    MeshPayload,
    tessellate_step,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = REPO_ROOT / "aturb.local.toml"
FIXTURE = REPO_ROOT / "packs" / "stub" / "fixtures" / "plate_2holes.step"


class _FakeShape:
    """A shape that tessellates into whatever the test asks for."""

    def __init__(self, vertices, triangles):
        self._vertices = vertices
        self._triangles = triangles

    def tessellate(self, tolerance, angular_tolerance):
        return self._vertices, self._triangles


class _FakeModel:
    """A model that holds one fake shape."""

    def __init__(self, vertices, triangles):
        self.shape = _FakeShape(vertices, triangles)


class _FakeVector:
    """A vertex with the three coordinates the tessellator returns."""

    def __init__(self, x, y, z):
        self.X = x
        self.Y = y
        self.Z = z


def test_the_defaults_are_the_documented_ones():
    """The starting defaults are the ones the phase recorded."""
    assert DEFAULT_TOLERANCE_MM == 0.1
    assert DEFAULT_ANGULAR_TOLERANCE_RAD == 0.1


def test_the_fixture_tessellates_into_a_valid_mesh():
    """The committed fixture tessellates into a valid triangle mesh."""
    mesh = tessellate_step(FIXTURE)

    assert isinstance(mesh, MeshPayload)
    assert mesh.vertex_count > 0
    assert mesh.triangle_count > 0
    assert len(mesh.positions) == 3 * mesh.vertex_count
    assert len(mesh.indices) == 3 * mesh.triangle_count
    assert all(0 <= index < mesh.vertex_count for index in mesh.indices)
    assert all(math.isfinite(value) for value in mesh.positions)


def test_the_fixture_mesh_has_the_measured_bounding_box():
    """The mesh of the fixture spans the 120 x 60 x 5 mm of the plate."""
    mesh = tessellate_step(FIXTURE)

    xs = mesh.positions[0::3]
    ys = mesh.positions[1::3]
    zs = mesh.positions[2::3]
    assert max(xs) - min(xs) == pytest.approx(120.0, abs=0.01)
    assert max(ys) - min(ys) == pytest.approx(60.0, abs=0.01)
    assert max(zs) - min(zs) == pytest.approx(5.0, abs=0.01)


def test_the_mesh_payload_is_json_ready():
    """The payload turns into JSON without a decoder."""
    mesh = tessellate_step(FIXTURE)

    payload = mesh.to_dict()

    assert set(payload) == {"positions", "indices",
                            "vertex_count", "triangle_count"}
    assert payload["positions"] == list(mesh.positions)
    assert payload["indices"] == list(mesh.indices)
    assert payload["vertex_count"] == mesh.vertex_count
    assert payload["triangle_count"] == mesh.triangle_count
    assert json.dumps(payload)


def test_a_missing_step_file_is_refused(tmp_path: Path):
    """A STEP file that is not there is refused."""
    with pytest.raises(MeshError):
        tessellate_step(tmp_path / "nowhere.step")


def test_a_broken_step_file_is_refused(tmp_path: Path):
    """A file that is not a STEP file is refused."""
    broken = tmp_path / "broken.step"
    broken.write_text("this is not a STEP file\n", encoding="utf-8")
    with pytest.raises(MeshError):
        tessellate_step(broken)


@pytest.mark.parametrize("tolerance", [0.0, -0.1])
def test_a_non_positive_tolerance_is_refused(tolerance: float):
    """A tolerance that is not positive is refused."""
    with pytest.raises(MeshError):
        tessellate_step(FIXTURE, tolerance=tolerance)


@pytest.mark.parametrize("angular_tolerance", [0.0, -0.1])
def test_a_non_positive_angular_tolerance_is_refused(angular_tolerance: float):
    """An angular tolerance that is not positive is refused."""
    with pytest.raises(MeshError):
        tessellate_step(FIXTURE, angular_tolerance=angular_tolerance)


def test_an_empty_tessellation_is_refused(monkeypatch):
    """A tessellation with no vertex is refused."""
    monkeypatch.setattr(
        "clients.viewer.mesh.load_step", lambda path: _FakeModel([], []))
    with pytest.raises(MeshError):
        tessellate_step(FIXTURE)


def test_a_tessellation_without_a_triangle_is_refused(monkeypatch):
    """A tessellation with vertices but no triangle is refused."""
    vertices = [_FakeVector(0.0, 0.0, 0.0)]
    monkeypatch.setattr(
        "clients.viewer.mesh.load_step", lambda path: _FakeModel(vertices, []))
    with pytest.raises(MeshError):
        tessellate_step(FIXTURE)


def test_an_index_outside_the_vertices_is_refused(monkeypatch):
    """A triangle index that points outside the vertices is refused."""
    vertices = [_FakeVector(0.0, 0.0, 0.0), _FakeVector(1.0, 0.0, 0.0)]
    monkeypatch.setattr(
        "clients.viewer.mesh.load_step",
        lambda path: _FakeModel(vertices, [(0, 1, 7)]))
    with pytest.raises(MeshError):
        tessellate_step(FIXTURE)


def test_a_non_finite_coordinate_is_refused(monkeypatch):
    """A coordinate that is not a finite number is refused."""
    vertices = [_FakeVector(0.0, 0.0, float("nan"))]
    monkeypatch.setattr(
        "clients.viewer.mesh.load_step",
        lambda path: _FakeModel(vertices, [(0, 0, 0)]))
    with pytest.raises(MeshError):
        tessellate_step(FIXTURE)


@pytest.mark.freecad
def test_a_built_part_tessellates_into_a_non_empty_mesh(tmp_path: Path):
    """A part built by the real backend exports a STEP that tessellates."""
    project = tmp_path / "proj"
    shutil.copytree(
        REPO_ROOT / "projects" / "demo",
        project,
        ignore=shutil.ignore_patterns("out"),
    )
    cfg = load_config(LOCAL_CONFIG)
    runner = load_runner("freecad", cfg, default_packs_root())

    result = runner.build(BuildRequest(
        project_root=str(project),
        part_id="plt0001",
        language=runner.info().language,
    ))

    assert result.status == "ok", result.error_text
    assert "step" in result.artifacts
    mesh = tessellate_step(project / result.artifacts["step"])

    assert isinstance(mesh, MeshPayload)
    assert mesh.vertex_count > 0
    assert mesh.triangle_count > 0
    assert len(mesh.positions) == 3 * mesh.vertex_count
    assert len(mesh.indices) == 3 * mesh.triangle_count
    assert all(0 <= index < mesh.vertex_count for index in mesh.indices)
    assert all(math.isfinite(value) for value in mesh.positions)
