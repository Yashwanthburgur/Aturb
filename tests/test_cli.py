"""Tests for the aturb build CLI using the stub pack."""

from __future__ import annotations

import shutil
from pathlib import Path

from aturb.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE_STUB = REPO_ROOT / "tests" / "fixtures" / "conformance" / "stub"


def write_config(tmp_path: Path) -> Path:
    """Write a tmp config with the stub pack active and return its path."""
    config = tmp_path / "aturb.local.toml"
    config.write_text(
        'active_pack = "stub"\n[packs.stub]\n[timeouts]\nbuild_s = 60\n',
        encoding="utf-8",
    )
    return config


def make_project(tmp_path: Path, part_text: str = "stub part file") -> Path:
    """Copy the stub conformance project into tmp_path and return its root."""
    project = tmp_path / "proj"
    shutil.copytree(CONFORMANCE_STUB, project)
    if part_text != "stub part file":
        (project / "parts" / "plt0001_base_plate.stub").write_text(
            part_text, encoding="utf-8")
    return project


def test_ok_build(tmp_path, capsys):
    """A good build prints a line starting 'ok plt0001' and returns 0."""
    project = make_project(tmp_path)
    code = main(["build", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("ok plt0001")


def test_scripted_failure(tmp_path, capsys):
    """A scripted timeout prints 'failed plt0001 timeout' and returns 1."""
    project = make_project(tmp_path, part_text="# STUB: fail=timeout")
    code = main(["build", str(project), "plt0001",
                 "--config", str(write_config(tmp_path))])
    out = capsys.readouterr().out
    assert code == 1
    assert out.startswith("failed plt0001 timeout")


def test_malformed_config_returns_2(tmp_path, capsys):
    """A malformed config file prints a clean error and returns 2."""
    config = tmp_path / "broken.toml"
    config.write_text('active_pack = "stub\n', encoding="utf-8")
    project = make_project(tmp_path)

    code = main(["build", str(project), "plt0001", "--config", str(config)])

    out = capsys.readouterr().out
    assert code == 2
    assert "invalid TOML" in out
    assert "Traceback" not in out


def test_missing_config_returns_2(tmp_path, capsys, monkeypatch):
    """A missing config file prints a message and returns 2."""
    monkeypatch.delenv("ATURB_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    project = make_project(tmp_path)
    code = main(["build", str(project), "plt0001"])
    capsys.readouterr()
    assert code == 2
