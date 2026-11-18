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
KILL_GRACE_S = 10  # starting default
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


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill a child process and everything it started, then release its pipes.

    Every wait here is bounded, so cleanup can never hang. This runs only after a
    timeout, and it never changes the timeout outcome; it just makes sure no
    process and no pipe is left behind.
    """
    tree_killed = False
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=KILL_GRACE_S,
        )
        tree_killed = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        tree_killed = False

    if not tree_killed:
        # Fallback when taskkill is unavailable or failed: kill the direct child.
        try:
            proc.kill()
        except OSError:
            pass

    # Reap the child and release the pipes, with a bounded wait.
    try:
        proc.communicate(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.communicate(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            pass


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

    proc = subprocess.Popen(
        [command, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REPO_ROOT),
        env=child_env,
    )
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        print("TIMEOUT")
        return EXIT_TIMEOUT

    print(f"EXIT: {proc.returncode}")
    print("--- STDOUT ---")
    print(stdout, end="")
    print("--- STDERR ---")
    print(stderr, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
