"""Tests for aturb.config. Test data uses the fake pack name "example"."""

from __future__ import annotations

import pytest

from aturb.config import (
    ConfigError,
    active_pack,
    load_config,
    pack_settings,
    timeout_s,
)

VALID_TOML = """
active_pack = "example"

[packs.example]
cmd = "example-runner"

[packs.other]

[timeouts]
build_s = 45
"""


def test_explicit_path_loads(tmp_path):
    cfg_file = tmp_path / "custom.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")

    cfg = load_config(cfg_file)

    assert cfg["active_pack"] == "example"
    assert cfg["packs"]["example"]["cmd"] == "example-runner"


def test_env_var_loads(tmp_path, monkeypatch):
    cfg_file = tmp_path / "from-env.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ATURB_CONFIG", str(cfg_file))

    cfg = load_config()

    assert cfg["active_pack"] == "example"


def test_missing_file_names_all_tried_locations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ATURB_CONFIG", raising=False)
    missing = tmp_path / "absent.toml"

    with pytest.raises(ConfigError) as excinfo:
        load_config(missing)

    message = str(excinfo.value)
    assert str(missing) in message
    assert "aturb.local.toml" in message


def test_active_pack_missing_raises():
    with pytest.raises(ConfigError):
        active_pack({})


def test_pack_settings_unknown_name_returns_empty():
    cfg = {"packs": {"example": {"cmd": "example-runner"}}}

    assert pack_settings(cfg, "other") == {}


def test_timeout_s_reads_build_s():
    cfg = {"timeouts": {"build_s": 45}}

    assert timeout_s(cfg) == 45
