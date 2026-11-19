"""Configuration loading for the ATURB core.

The core is CAD-neutral, so this module never mentions any CAD system. It finds a
TOML file and reads a few well-known keys from it; everything CAD-specific lives in
the pack section named by ``active_pack``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

LOCAL_CONFIG_NAME = "aturb.local.toml"
ENV_VAR_NAME = "ATURB_CONFIG"


class ConfigError(Exception):
    """Raised when configuration cannot be found or is missing a required key."""


def _candidate_paths(path: Path | None) -> list[Path]:
    """Return the config locations to try, in search order."""
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    from_env = os.environ.get(ENV_VAR_NAME)
    if from_env:
        candidates.append(Path(from_env))
    candidates.append(Path.cwd() / LOCAL_CONFIG_NAME)
    return candidates


def load_config(path: Path | None = None) -> dict:
    """Load configuration.

    Search order: the explicit ``path`` if given, then the file named by the
    ``ATURB_CONFIG`` environment variable, then ``aturb.local.toml`` in the current
    working directory. The first file that exists is used. If none exists, raise
    ``ConfigError`` listing every location that was tried. A file that is not
    valid TOML also raises ``ConfigError``.
    """
    candidates = _candidate_paths(path)
    for candidate in candidates:
        if candidate.is_file():
            try:
                with candidate.open("rb") as handle:
                    return tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(
                    f"invalid TOML in {candidate}: {exc}") from exc
    tried = ", ".join(str(candidate) for candidate in candidates)
    raise ConfigError(f"no configuration file found; tried: {tried}")


def active_pack(cfg: dict) -> str:
    """Return the name of the active pack; raise if it is missing."""
    try:
        return cfg["active_pack"]
    except KeyError:
        raise ConfigError("missing 'active_pack' in configuration") from None


def pack_settings(cfg: dict, name: str) -> dict:
    """Return the settings section for one pack, or an empty dict if absent."""
    return cfg.get("packs", {}).get(name, {})


def timeout_s(cfg: dict, kind: str = "build") -> int:
    """Return the timeout in seconds for one operation kind (e.g. "build")."""
    key = f"{kind}_s"
    try:
        return int(cfg["timeouts"][key])
    except KeyError:
        raise ConfigError(
            f"missing 'timeouts.{key}' in configuration") from None
