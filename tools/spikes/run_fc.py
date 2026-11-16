"""Run a script inside headless FreeCAD, so shell quoting never gets in the way.

Usage:
  uv run python tools/spikes/run_fc.py <script.py> [--env KEY=VALUE ...] [--timeout SECONDS]

The command is read from the active configuration: the "cmd" key of the [packs.freecad]
section (see aturb.example.toml and docs/ENVIRONMENT.md).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from aturb.config import ConfigError, load_config, pack_settings

DEFAULT_TIMEOUT_S = 120  # starting default
PACK_NAME = "freecad"

# Exit codes used by this script.
EXIT_CONFIG = 2
EXIT_TIMEOUT = 3

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_env_pairs(pairs: list[str]) -> dict[str, str]:
    """Turn ["KEY=VALUE", ...] into {"KEY": "VALUE"}. Bad pairs exit with code 2."""
    parsed: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key:
            print(
                f"error: --env expects KEY=VALUE, got {pair!r}", file=sys.stderr)
            raise SystemExit(EXIT_CONFIG)
        parsed[key] = value
    return parsed


def _resolve_command() -> str:
    """Read the CAD command from configuration, or exit with a clear message."""
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from None
    command = pack_settings(cfg, PACK_NAME).get("cmd", "")
    if not command:
        print(
            f"error: packs.{PACK_NAME}.cmd is not set in the configuration "
            "(copy aturb.example.toml to aturb.local.toml and fill it in; "
            "see docs/ENVIRONMENT.md)",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CONFIG)
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a script inside headless FreeCAD and show its output.",
    )
    parser.add_argument(
        "script", help="Path to the script to run inside FreeCAD.")
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra environment variable for the child process (repeatable).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help=f"Seconds to wait before giving up (default {DEFAULT_TIMEOUT_S}).",
    )
    args = parser.parse_args(argv)

    extra_env = _parse_env_pairs(args.env)
    command = _resolve_command()

    script_path = Path(args.script).resolve()
    child_env = os.environ.copy()
    child_env.update(extra_env)

    try:
        completed = subprocess.run(
            [command, str(script_path)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=child_env,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return EXIT_TIMEOUT

    print(f"EXIT: {completed.returncode}")
    print("--- STDOUT ---")
    print(completed.stdout, end="")
    print("--- STDERR ---")
    print(completed.stderr, end="")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
