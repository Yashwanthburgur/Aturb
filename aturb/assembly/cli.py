"""The `aturb assemble` and `aturb edit-assembly` commands.

The `assemble` command builds every part of the assembly through the active
pack, verifies the assembly as a whole and prints one line about the outcome.
The `edit-assembly` command asks the model for the new source of the parts
that must change, applies the change through the safe assembly edit and
records the revision of the assembly.

The exit codes are the ones of the other commands: 0 when the assembly
verifies, 1 when it does not, and 2 for a configuration, a pack or a manifest
error.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aturb.agent.config import agent_settings, read_api_key
from aturb.agent.model import HttpModelClient
from aturb.agent.types import AgentError
from aturb.assembly.manifest import AssemblyError
from aturb.config import ConfigError, active_pack, load_config, timeout_s
from aturb.contract.runner import Runner
from aturb.packs import PackError, default_packs_root, discover, load_runner

PROMPT_FILE_NAME = "agent.md"


def add_assembly_parsers(subparsers) -> None:
    """Register the assembly commands on the parser of the core."""
    assemble = subparsers.add_parser("assemble")
    assemble.add_argument("project_dir")
    assemble.add_argument("assembly_file")
    assemble.add_argument("--config", default=None)
    edit = subparsers.add_parser("edit-assembly")
    edit.add_argument("project_dir")
    edit.add_argument("assembly_file")
    edit.add_argument("instruction")
    edit.add_argument("--config", default=None)


def run_assemble_command(
    args: argparse.Namespace,
    runner: Runner,
    timeout: int,
) -> int:
    """Build and verify one assembly and print one line about the outcome."""
    from aturb.assembly.build import build_assembly

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


def run_edit_assembly_command(args: argparse.Namespace) -> int:
    """Edit the parts of an assembly with the model and print the outcome.

    The command loads the configuration, the active pack and the model client
    of the configuration, asks the model for the new source of the parts that
    must change and records the revision of the assembly. A change that does
    not verify is never promoted: the command reports the failure and the
    live project stays as it was.
    """
    from aturb.assembly.agent import edit_assembly

    project = Path(args.project_dir).resolve()
    try:
        cfg = load_config(Path(args.config) if args.config else None)
        name = active_pack(cfg)
        packs_root = default_packs_root()
        runner = load_runner(name, cfg, packs_root)
        settings = agent_settings(cfg)
        client = HttpModelClient.from_settings(
            settings, read_api_key(settings))
        result = edit_assembly(
            project, Path(args.assembly_file), args.instruction,
            client=client, runner=runner, settings=settings,
            pack_prompt=_pack_prompt(packs_root, name),
            timeout_s=timeout_s(cfg), record_revision=True)
    except (ConfigError, PackError, AssemblyError, AgentError) as exc:
        print(str(exc))
        return 2
    if result.status != "ok":
        print(f"failed {result.assembly_id} ({result.stop_reason}): "
              f"{_first_line(result.error)}")
        return 1
    updated = ",".join(result.updated_parts)
    print(f"ok {result.assembly_id} revision={result.revision_id} "
          f"attempts={result.attempts} updated={updated}")
    return 0


def _pack_prompt(packs_root: Path, name: str) -> str:
    """Return the prompt of the pack, read from the folder of the pack."""
    manifest = discover(packs_root)[name]
    path = manifest.pack_dir / manifest.prompt_dir / PROMPT_FILE_NAME
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PackError(f"cannot read the pack prompt {path}: {exc}") from exc


def _first_line(text: str) -> str:
    """Return the first line of a text, or the text when it has one line."""
    lines = text.splitlines()
    return lines[0] if lines else ""
