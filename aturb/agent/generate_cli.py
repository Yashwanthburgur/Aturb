"""The thin command-line client for expectation-free generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aturb.agent.config import agent_settings
from aturb.agent.generate import DEFAULT_PART_ID, GenerateResult, generate_part
from aturb.agent.record import toml_string
from aturb.agent.types import AgentError
from aturb.config import ConfigError, active_pack, timeout_s
from aturb.evals.judge import sanitize_text
from aturb.packs import PackError, discover, load_runner

DEFAULT_OUT_ROOT = Path("evals/tmp/generate")  # starting default
STAMP_FORMAT = "%Y-%m-%d_%H%M%S"


def add_generate_parser(subparsers) -> None:
    """Register the generate subcommand without changing other commands."""
    parser = subparsers.add_parser("generate")
    parser.add_argument("prompt", nargs="?", default=None)
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--part-id", default=DEFAULT_PART_ID)
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--pack", default=None)


def write_generate_manifest(result: GenerateResult) -> Path:
    """Write a portable result.toml at the workspace root."""
    workspace = result.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    lines = [
        f"status = {toml_string(result.status)}",
        f"part_id = {toml_string(result.part_id)}",
        f"stop_reason = {toml_string(result.stop_reason)}",
        f"attempts = {result.attempts}",
        f"input_tokens = {result.input_tokens}",
        f"output_tokens = {result.output_tokens}",
        f"cost_usd = {float(result.cost_usd)!r}",
        f"prompt_version = {toml_string(result.prompt_version)}",
        f"build_status = {toml_string(result.build_status)}",
        f"failure_kind = {toml_string(result.failure_kind)}",
        f"error = {toml_string(sanitize_text(result.error))}",
        f"conventions = {_strings(result.conventions)}",
        f"part_file = {toml_string(_relative(workspace, result.part_path))}",
        f"step_file = {toml_string(_relative(workspace, result.step_path))}",
        f"native_file = {toml_string(_relative(workspace, result.native_path))}",
    ]
    if result.geometry is not None:
        geometry = result.geometry
        lines.extend([
            f"is_valid = {_bool(geometry.is_valid)}",
            f"is_single_solid = {_bool(geometry.is_single_solid)}",
            f"volume = {float(geometry.volume)!r}",
            "bbox_size = [" + ", ".join(
                repr(float(value)) for value in geometry.bbox_size) + "]",
            f"hole_count = {len(geometry.holes)}",
            f"holes = {_holes(geometry.holes)}",
        ])
    path = workspace / "result.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def format_generate_report(result: GenerateResult) -> str:
    """Return a scannable engineering report with no correctness score."""
    lines = [
        f"Status: {result.status}",
        f"Stop reason: {result.stop_reason}",
        f"Part: {result.part_id}",
        f"Attempts: {result.attempts}",
        f"Tokens: {result.input_tokens} in / {result.output_tokens} out",
        f"Cost (USD): {result.cost_usd:.6f}",
        f"Prompt version: {result.prompt_version or 'not called'}",
    ]
    if result.build_status:
        lines.append(f"Build: {result.build_status}")
    if result.failure_kind:
        lines.append(f"Failure kind: {result.failure_kind}")
    lines.extend([
        "Saved files:",
        f"  source: {_relative(result.workspace, result.part_path) or 'not produced'}",
        f"  STEP: {_relative(result.workspace, result.step_path) or 'not produced'}",
        f"  native: {_relative(result.workspace, result.native_path) or 'not produced'}",
        "  manifest: result.toml",
    ])
    if result.geometry is not None:
        geometry = result.geometry
        lines.extend([
            "Measured geometry:",
            f"  is_valid: {_bool(geometry.is_valid)}",
            f"  is_single_solid: {_bool(geometry.is_single_solid)}",
            f"  volume: {_number(geometry.volume)} mm^3",
            "  bbox_size: " + " x ".join(
                _number(value) for value in geometry.bbox_size) + " mm",
            f"  holes: {len(geometry.holes)}",
        ])
        for index, hole in enumerate(geometry.holes, start=1):
            lines.append(
                f"    hole {index}: diameter {_number(hole.diameter)} mm, "
                f"position ({_number(hole.x)}, {_number(hole.y)}) mm")
    if result.conventions:
        lines.append("Advisory convention findings:")
        lines.extend(f"  {finding}" for finding in result.conventions)
    if result.error:
        lines.append(f"Error: {sanitize_text(result.error)}")
    return "\n".join(lines)


def run_generate_command(args, cfg, packs_root, client_factory) -> int:
    """Resolve one request, run generation, write its manifest and report it."""
    if bool(args.prompt) == bool(args.prompt_file):
        print("supply exactly one of a positional prompt or --prompt-file")
        return 2
    try:
        requirement = (args.prompt_file.read_text(encoding="utf-8")
                       if args.prompt_file else args.prompt)
    except (OSError, UnicodeError) as exc:
        print(f"the prompt file could not be read: {exc}")
        return 2
    if args.max_attempts is not None and args.max_attempts < 1:
        print("--max-attempts must be at least 1")
        return 2
    out_dir = args.out or DEFAULT_OUT_ROOT / datetime.now().strftime(STAMP_FORMAT)
    try:
        settings = agent_settings(cfg)
        if args.max_attempts is not None:
            settings["max_attempts"] = args.max_attempts
        name = args.pack or active_pack(cfg)
        manifests = discover(packs_root)
        if name not in manifests:
            raise PackError(f"unknown pack {name!r}")
        runner = load_runner(name, cfg, packs_root)
        client = client_factory(settings)
        result = generate_part(
            requirement, out_dir, client, runner, settings, manifests[name],
            timeout_s(cfg), part_id=args.part_id)
        write_generate_manifest(result)
    except (AgentError, ConfigError, PackError, OSError, ValueError) as exc:
        print(str(exc))
        return 2
    print(format_generate_report(result))
    return 0 if result.status == "ok" else 1


def _relative(workspace: Path, path: Path | None) -> str:
    if path is None:
        return ""
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _strings(items) -> str:
    return "[" + ", ".join(toml_string(item) for item in items) + "]"


def _holes(holes) -> str:
    entries = [
        "{ diameter = " + repr(float(hole.diameter))
        + ", x = " + repr(float(hole.x)) + ", y = " +
        repr(float(hole.y)) + " }"
        for hole in holes
    ]
    return "[" + ", ".join(entries) + "]"


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")
