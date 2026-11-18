"""Tests for pack manifest loading, discovery and runner loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.contract import CONTRACT_VERSION
from aturb.packs import (
    PackError,
    discover,
    load_manifest,
    load_runner,
)

FAKE_RUNNER_SOURCE = '''"""A fake runner used by the pack loading tests."""

from aturb.contract.types import BuildResult, PackInfo


class ExampleRunner:
    """A runner that records how it was constructed."""

    def __init__(self, settings, pack_dir):
        self.settings = settings
        self.pack_dir = pack_dir

    def info(self):
        return PackInfo(name="example", language="python", version="0.1")

    def build(self, request):
        return BuildResult(status="ok")
'''


def manifest_text(
    module_name: str,
    contract_version: str = CONTRACT_VERSION,
    name: str = "example",
) -> str:
    """Return the TOML text of a valid fake pack manifest."""
    return (
        f'name = "{name}"\n'
        'language = "python"\n'
        'part_extension = ".py"\n'
        f'runner = "{module_name}:ExampleRunner"\n'
        'prompt_dir = "prompts"\n'
        f'contract_version = "{contract_version}"\n'
    )


def write_manifest(pack_dir: Path, text: str) -> Path:
    """Write a pack.toml into pack_dir and return its path."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    path = pack_dir / "pack.toml"
    path.write_text(text, encoding="utf-8")
    return path


def make_fake_pack(tmp_path, monkeypatch, contract_version=CONTRACT_VERSION):
    """Create a fake pack whose runner module is importable.

    Returns (packs_root, pack_dir). The runner module name is unique per
    test, so one test's import cannot leak into another.
    """
    packs_root = tmp_path / "packs"
    pack_dir = packs_root / "example"
    pack_dir.mkdir(parents=True)
    module_name = f"fake_runner_{tmp_path.name}"
    (pack_dir / f"{module_name}.py").write_text(
        FAKE_RUNNER_SOURCE, encoding="utf-8")
    write_manifest(pack_dir, manifest_text(module_name, contract_version))
    monkeypatch.syspath_prepend(str(pack_dir))
    return packs_root, pack_dir


def test_valid_manifest_loads(tmp_path):
    """A complete manifest loads into a PackManifest."""
    path = write_manifest(
        tmp_path / "example", manifest_text("fake_runner"))

    manifest = load_manifest(path)

    assert manifest.name == "example"
    assert manifest.language == "python"
    assert manifest.part_extension == ".py"
    assert manifest.runner == "fake_runner:ExampleRunner"
    assert manifest.prompt_dir == "prompts"
    assert manifest.contract_version == CONTRACT_VERSION
    assert manifest.pack_dir == tmp_path / "example"


def test_missing_key_is_rejected(tmp_path):
    """A manifest without a required key raises PackError naming that key."""
    path = write_manifest(tmp_path / "example", 'name = "example"\n')

    with pytest.raises(PackError) as excinfo:
        load_manifest(path)

    assert "language" in str(excinfo.value)


def test_unknown_key_is_rejected(tmp_path):
    """A manifest with an unknown key raises PackError naming that key."""
    text = manifest_text("fake_runner") + 'extra = "x"\n'
    path = write_manifest(tmp_path / "example", text)

    with pytest.raises(PackError) as excinfo:
        load_manifest(path)

    assert "extra" in str(excinfo.value)


def test_discover_finds_pack(tmp_path, monkeypatch):
    """discover() finds a pack folder that holds a pack.toml."""
    packs_root, _ = make_fake_pack(tmp_path, monkeypatch)

    manifests = discover(packs_root)

    assert "example" in manifests
    assert manifests["example"].name == "example"


def test_discover_skips_underscore_folders(tmp_path, monkeypatch):
    """Folders whose names start with an underscore are skipped."""
    packs_root, _ = make_fake_pack(tmp_path, monkeypatch)
    write_manifest(
        packs_root / "_private",
        manifest_text("fake_runner", name="hidden"),
    )

    manifests = discover(packs_root)

    assert set(manifests) == {"example"}


def test_load_runner_builds_instance(tmp_path, monkeypatch):
    """load_runner() returns a runner built with the pack's settings."""
    packs_root, pack_dir = make_fake_pack(tmp_path, monkeypatch)
    cfg = {"packs": {"example": {"cmd": "example-runner"}}}

    runner = load_runner("example", cfg, packs_root)

    assert runner.settings == {"cmd": "example-runner"}
    assert runner.pack_dir == pack_dir


def test_load_runner_rejects_wrong_contract_version(tmp_path, monkeypatch):
    """A pack built for another contract version is rejected."""
    packs_root, _ = make_fake_pack(
        tmp_path, monkeypatch, contract_version="9.9")

    with pytest.raises(PackError) as excinfo:
        load_runner("example", {}, packs_root)

    message = str(excinfo.value)
    assert "9.9" in message
    assert CONTRACT_VERSION in message


def test_load_runner_rejects_unknown_pack(tmp_path, monkeypatch):
    """An unknown pack name is rejected and the available names are listed."""
    packs_root, _ = make_fake_pack(tmp_path, monkeypatch)

    with pytest.raises(PackError) as excinfo:
        load_runner("missing", {}, packs_root)

    message = str(excinfo.value)
    assert "missing" in message
    assert "example" in message
