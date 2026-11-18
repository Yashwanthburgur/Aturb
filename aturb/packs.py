"""Pack discovery and runner loading.

The core never imports a pack statically. It reads each pack's manifest and
loads the runner module that the manifest names.
"""

from __future__ import annotations

import importlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

from aturb.config import pack_settings
from aturb.contract import CONTRACT_VERSION

REQUIRED_KEYS = {
    "name",
    "language",
    "part_extension",
    "runner",
    "prompt_dir",
    "contract_version",
}


class PackError(Exception):
    """Raised when a pack cannot be found, read or loaded."""


@dataclass(frozen=True)
class PackManifest:
    """What a pack's pack.toml says about itself."""

    name: str
    language: str
    part_extension: str
    runner: str
    prompt_dir: str
    contract_version: str
    pack_dir: Path


def load_manifest(path: Path) -> PackManifest:
    """Read one pack.toml and return the manifest it describes.

    Raises PackError if a required key is missing, if an unknown key is
    present, or if the file cannot be read as TOML.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise PackError(f"cannot read pack manifest {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PackError(f"invalid TOML in {path}: {exc}") from exc

    missing = sorted(REQUIRED_KEYS - data.keys())
    if missing:
        raise PackError(
            f"pack manifest {path} is missing key(s): {', '.join(missing)}")
    unknown = sorted(data.keys() - REQUIRED_KEYS)
    if unknown:
        raise PackError(
            f"pack manifest {path} has unknown key(s): {', '.join(unknown)}")

    return PackManifest(
        name=data["name"],
        language=data["language"],
        part_extension=data["part_extension"],
        runner=data["runner"],
        prompt_dir=data["prompt_dir"],
        contract_version=data["contract_version"],
        pack_dir=path.parent,
    )


def discover(packs_root: Path) -> dict[str, PackManifest]:
    """Load every pack manifest under packs_root, keyed by manifest name.

    Folders whose names start with an underscore are skipped. Two packs that
    claim the same name are an error.
    """
    packs_root = Path(packs_root)
    manifests: dict[str, PackManifest] = {}
    if not packs_root.is_dir():
        return manifests
    for folder in sorted(packs_root.iterdir()):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        manifest_path = folder / "pack.toml"
        if not manifest_path.is_file():
            continue
        manifest = load_manifest(manifest_path)
        if manifest.name in manifests:
            raise PackError(
                f"duplicate pack name {manifest.name!r}: "
                f"{manifests[manifest.name].pack_dir} and "
                f"{manifest.pack_dir}")
        manifests[manifest.name] = manifest
    return manifests


def load_runner(name: str, cfg: dict, packs_root: Path):
    """Load the runner of one pack by name.

    The runner module is imported dynamically from the manifest, so the core
    never imports a pack statically.
    """
    manifests = discover(packs_root)
    if name not in manifests:
        available = ", ".join(sorted(manifests)) or "none"
        raise PackError(
            f"unknown pack {name!r}; available packs: {available}")
    manifest = manifests[name]
    if manifest.contract_version != CONTRACT_VERSION:
        raise PackError(
            f"pack {name!r} speaks contract version "
            f"{manifest.contract_version!r}, but this core speaks "
            f"{CONTRACT_VERSION!r}")
    module_path, _, class_name = manifest.runner.partition(":")
    if not module_path or not class_name:
        raise PackError(
            f"pack {name!r} has an invalid runner entry "
            f"{manifest.runner!r}; expected 'module:Class'")
    module = importlib.import_module(module_path)
    runner_class = getattr(module, class_name)
    return runner_class(
        settings=pack_settings(cfg, name),
        pack_dir=manifest.pack_dir,
    )


def default_packs_root() -> Path:
    """Return the packs folder next to the aturb package."""
    return Path(__file__).resolve().parent.parent / "packs"
