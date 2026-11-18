"""Conformance suite every backend pack must pass.

PACKS is ["stub"] plus any comma-separated names in ATURB_CONFORMANCE_PACKS.
FreeCAD parameters are marked with pytest.mark.freecad automatically.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from pathlib import Path

import pytest

from aturb.config import ConfigError, load_config, pack_settings
from aturb.contract import CONTRACT_VERSION
from aturb.contract.types import BuildRequest
from aturb.packs import default_packs_root, load_runner
from aturb.workspace.paths import resolve_inside

REPO_ROOT = Path(__file__).resolve().parents[2]

PACKS = ["stub"] + [
    name.strip()
    for name in os.environ.get("ATURB_CONFORMANCE_PACKS", "").split(",")
    if name.strip()
]


def conformance_project(pack: str) -> Path:
    """Return the source project folder for one pack's conformance run."""
    if pack == "stub":
        return REPO_ROOT / "tests" / "fixtures" / "conformance" / "stub"
    if pack == "freecad":
        return REPO_ROOT / "projects" / "demo"
    raise ValueError(f"no conformance project for pack {pack!r}")


def freecad_config() -> tuple[dict, str]:
    """Return the FreeCAD pack settings and the reason to skip, if any.

    The FreeCAD pack needs a machine-specific command, so its settings come
    from the local config file. When that file is missing or invalid the pack
    is skipped with the reason, so the suite never depends on one machine and
    never hides an unrelated configuration error.
    """
    config_path = REPO_ROOT / "aturb.local.toml"
    if not config_path.is_file():
        return {"packs": {}}, "no local configuration file"
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        return {"packs": {}}, f"unreadable local configuration: {exc}"
    except tomllib.TOMLDecodeError as exc:
        return {"packs": {}}, f"invalid TOML in the local configuration: {exc}"
    except OSError as exc:
        return {"packs": {}}, f"unreadable local configuration: {exc}"
    if not pack_settings(cfg, "freecad").get("cmd"):
        return {"packs": {}}, "packs.freecad.cmd is not configured"
    return cfg, ""


def pack_config(pack: str) -> dict:
    """Return the config used to load one pack's runner."""
    if pack == "freecad":
        return freecad_config()[0]
    return {"packs": {}}


@pytest.fixture(params=PACKS)
def pack(request, tmp_path):
    """Yield (pack_name, runner, tmp project root)."""
    name = request.param
    if name == "freecad":
        request.applymarker(pytest.mark.freecad)
        cfg, reason = freecad_config()
        if reason:
            pytest.skip(f"freecad conformance skipped: {reason}")
    else:
        cfg = pack_config(name)
    runner = load_runner(name, cfg, default_packs_root())
    project = tmp_path / "proj"
    shutil.copytree(conformance_project(name), project)
    return name, runner, project


def build_request(runner, project: Path, part_id="plt0001", language=None):
    """Build a request using the runner's own language."""
    return BuildRequest(
        project_root=str(project),
        part_id=part_id,
        language=language or runner.info().language,
    )


def test_info_is_complete(pack):
    """info() returns non-empty name, language and version."""
    _, runner, _ = pack
    info = runner.info()
    assert info.name and info.language and info.version


def test_build_ok(pack):
    """Building plt0001 returns status ok."""
    _, runner, project = pack
    result = runner.build(build_request(runner, project))
    assert result.status == "ok", result.error_text


def test_artifacts_exist_inside_project(pack):
    """Both artifacts exist and resolve inside the project."""
    _, runner, project = pack
    result = runner.build(build_request(runner, project))
    assert result.status == "ok", result.error_text
    for key in ("native", "step"):
        assert key in result.artifacts
        assert resolve_inside(project, result.artifacts[key]).is_file()


def test_result_round_trips(pack):
    """BuildResult.from_dict(result.to_dict()) == result."""
    from aturb.contract.types import BuildResult
    _, runner, project = pack
    result = runner.build(build_request(runner, project))
    assert BuildResult.from_dict(result.to_dict()) == result


def test_duration_and_contract_version(pack):
    """duration_ms >= 0 and contract_version matches the core."""
    _, runner, project = pack
    result = runner.build(build_request(runner, project))
    assert result.duration_ms >= 0
    assert result.contract_version == CONTRACT_VERSION


def test_wrong_language_is_input_error(pack):
    """A request in the wrong language returns INPUT_ERROR."""
    from aturb.contract.types import FailureKind
    _, runner, project = pack
    result = runner.build(
        build_request(runner, project, language="not-the-language"))
    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR


def test_unknown_part_is_input_error(pack):
    """A request for a missing part returns INPUT_ERROR."""
    from aturb.contract.types import FailureKind
    _, runner, project = pack
    result = runner.build(build_request(runner, project, part_id="zzz9999"))
    assert result.status == "failed"
    assert result.failure_kind is FailureKind.INPUT_ERROR


def test_pack_config_without_a_local_file(monkeypatch, tmp_path):
    """Without a local config file the FreeCAD pack gets empty settings."""
    import tests.contract.test_conformance as conformance
    monkeypatch.setattr(conformance, "REPO_ROOT", tmp_path)
    assert conformance.pack_config("freecad") == {"packs": {}}
    _, reason = conformance.freecad_config()
    assert "no local configuration file" in reason


def test_pack_config_with_invalid_toml(monkeypatch, tmp_path):
    """A malformed local config file is reported, not hidden."""
    import tests.contract.test_conformance as conformance
    (tmp_path / "aturb.local.toml").write_text(
        "active_pack = 'freecad\n", encoding="utf-8")
    monkeypatch.setattr(conformance, "REPO_ROOT", tmp_path)
    assert conformance.pack_config("freecad") == {"packs": {}}
    _, reason = conformance.freecad_config()
    assert "invalid TOML" in reason
