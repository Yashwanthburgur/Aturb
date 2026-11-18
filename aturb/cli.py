"""Command line interface: aturb build <project_dir> <part_id> [--config PATH]."""

from __future__ import annotations

import argparse
from pathlib import Path

from aturb.config import ConfigError, active_pack, load_config, timeout_s
from aturb.contract.types import BuildRequest
from aturb.packs import PackError, default_packs_root, load_runner


def main(argv: list[str] | None = None) -> int:
    """Run one build through the active pack and print a one-line result."""
    parser = argparse.ArgumentParser(prog="aturb")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("project_dir")
    build.add_argument("part_id")
    build.add_argument("--config", default=None)
    args = parser.parse_args(argv)

    try:
        cfg = load_config(Path(args.config) if args.config else None)
        name = active_pack(cfg)
        runner = load_runner(name, cfg, default_packs_root())
        request = BuildRequest(
            project_root=str(Path(args.project_dir).resolve()),
            part_id=args.part_id,
            language=runner.info().language,
            timeout_s=timeout_s(cfg),
        )
    except (ConfigError, PackError) as exc:
        print(str(exc))
        return 2

    result = runner.build(request)
    if result.status == "ok":
        print(
            f"ok {args.part_id} {result.duration_ms}ms "
            f"step={result.artifacts.get('step', '')}")
        return 0
    first_line = result.error_text.splitlines()[0] if result.error_text else ""
    print(f"failed {args.part_id} {result.failure_kind.value}: {first_line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
