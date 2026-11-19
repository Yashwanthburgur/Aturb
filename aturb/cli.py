"""Command line interface: aturb build and aturb check.

Both commands build a part through the active pack. ``build`` reports the
build; ``check`` then runs the neutral checks over the exported STEP and
prints one line per check.

The expected values of a part live in ``<project_dir>/expect/<part_id>.toml``.
They hold numbers only, so the same file judges a part whatever built it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aturb.config import ConfigError, active_pack, load_config, timeout_s
from aturb.contract.types import BuildRequest, BuildResult
from aturb.packs import PackError, default_packs_root, load_runner
from aturb.verify.result import CheckResult

EXPECT_DIR = "expect"


def main(argv: list[str] | None = None) -> int:
    """Run one build or one check through the active pack."""
    parser = argparse.ArgumentParser(prog="aturb")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("project_dir")
    build.add_argument("part_id")
    build.add_argument("--config", default=None)
    check = sub.add_parser("check")
    check.add_argument("project_dir")
    check.add_argument("part_id")
    check.add_argument("--config", default=None)
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
    if result.status != "ok":
        return _report_failure(args.part_id, result)
    if args.command == "check":
        return _run_checks(args.part_id, Path(request.project_root), result)
    return _report_success(args.part_id, result)


def _report_success(part_id: str, result: BuildResult) -> int:
    """Print the one-line result of a successful build."""
    print(
        f"ok {part_id} {result.duration_ms}ms "
        f"step={result.artifacts.get('step', '')}")
    return 0


def _report_failure(part_id: str, result: BuildResult) -> int:
    """Print the one-line result of a failed build."""
    first_line = result.error_text.splitlines()[0] if result.error_text else ""
    kind = result.failure_kind.value if result.failure_kind else "unknown"
    print(f"failed {part_id} {kind}: {first_line}")
    return 1


def _run_checks(part_id: str, project: Path, result: BuildResult) -> int:
    """Run the neutral checks over the exported STEP and print one line each.

    The expected values of the part are read from the project. A part whose
    expected values or whose STEP cannot be read has no check that can pass,
    so the command reports a failed check and returns 1.

    The measuring library is imported here and not at the top of the file, so
    that a plain build does not pay for loading it.
    """
    from aturb.verify.expectations import (
        checks_from_expectations,
        load_expectations,
    )
    from aturb.verify.step import StepLoadError, load_step

    expect_path = project / EXPECT_DIR / f"{part_id}.toml"
    try:
        expected = load_expectations(expect_path)
    except FileNotFoundError:
        print(
            f"check expectations failed: no expectation file at {expect_path}")
        return 1
    except (OSError, ValueError) as exc:
        print(f"check expectations failed: {exc}")
        return 1

    step_rel = result.artifacts.get("step")
    if not step_rel:
        print("check step failed: the build produced no STEP file")
        return 1
    try:
        model = load_step(project / step_rel)
    except StepLoadError as exc:
        print(f"check step failed: {exc}")
        return 1

    results = checks_from_expectations(model, expected)
    for check_result in results:
        print(_check_line(check_result))
    return 0 if all(result.passed for result in results) else 1


def _check_line(result: CheckResult) -> str:
    """One line for one check result."""
    if result.passed:
        return f"check {result.name} passed"
    return f"check {result.name} failed: {_failure_text(result)}"


def _failure_text(result: CheckResult) -> str:
    """Say why a check failed."""
    if result.message:
        return result.message
    if result.expected is None or result.actual is None:
        return "the check could not be measured"
    return f"expected {result.expected}, got {result.actual}"


if __name__ == "__main__":
    raise SystemExit(main())
