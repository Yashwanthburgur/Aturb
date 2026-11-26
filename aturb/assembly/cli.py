"""The `aturb assemble` command: build and verify one assembly.

The command builds every part of the assembly through the active pack, verifies
the assembly as a whole and prints one line about the outcome. The exit codes
are the ones of the other commands: 0 when the assembly verifies, 1 when it
does not, and 2 for a configuration, a pack or a manifest error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aturb.assembly.build import build_assembly
from aturb.assembly.manifest import AssemblyError
from aturb.contract.runner import Runner


def run_assemble_command(
    args: argparse.Namespace,
    runner: Runner,
    timeout: int,
) -> int:
    """Build and verify one assembly and print one line about the outcome."""
    project = Path(args.project_dir).resolve()
    try:
        result = build_assembly(
            project, Path(args.assembly_file), runner, timeout_s=timeout)
    except AssemblyError as exc:
        print(str(exc))
        return 2
    if result.status != "ok":
        print(f"failed {result.assembly_id}: {_first_line(result.error)}")
        return 1
    count = result.report.component_count if result.report else 0
    print(f"ok {result.assembly_id} components={count} interference=no "
          f"step={result.assembly_step}")
    return 0


def _first_line(text: str) -> str:
    """Return the first line of a text, or the text when it has one line."""
    lines = text.splitlines()
    return lines[0] if lines else ""
