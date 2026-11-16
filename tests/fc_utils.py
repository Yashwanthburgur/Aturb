"""FreeCAD test utilities for running the spike harness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

# Load config from the aturb package
from aturb.config import load_config, pack_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_S = 120  # starting default
HARNESS_PATH = REPO_ROOT / "tools" / "spikes" / "fc_build.py"


def run_spike_build(part_path: Path, out_dir: Path) -> dict:
    """
    Run the spike harness on a part file and return the parsed RESULT JSON.

    Args:
        part_path: Absolute path to the part file to build.
        out_dir: Absolute output directory (will be created).

    Returns:
        Parsed JSON dict from the RESULT: line in stdout.

    Raises:
        AssertionError: If no RESULT line is found in stdout.
        subprocess.CalledProcessError: If the process times out.
    """
    # Load config with explicit path to root's aturb.local.toml
    config_path = REPO_ROOT / "aturb.local.toml"
    cfg = load_config(config_path)

    # Get the FreeCAD command from pack settings
    freecad_settings = pack_settings(cfg, "freecad")
    cmd = freecad_settings.get("cmd", "")
    if not cmd:
        raise AssertionError(
            "packs.freecad.cmd is not configured in aturb.local.toml")

    # Ensure absolute paths
    part_path = part_path.resolve()
    out_dir = out_dir.resolve()

    # Run the harness
    env = {
        **os.environ,
        "ATURB_PART": str(part_path),
        "ATURB_OUT": str(out_dir),
    }

    result = subprocess.run(
        [cmd, str(HARNESS_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=DEFAULT_TIMEOUT_S,
    )

    # Find the RESULT line
    stdout_lines = result.stdout.splitlines()
    result_line = None
    for line in stdout_lines:
        if line.startswith("RESULT: "):
            result_line = line[len("RESULT: "):]
            break

    if result_line is None:
        raise AssertionError(
            f"No RESULT line found in stdout.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return json.loads(result_line)
