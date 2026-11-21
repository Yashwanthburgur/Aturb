"""Command line interface: aturb build, aturb check and aturb eval.

The build and check commands build a part through the active pack. ``build``
reports the build; ``check`` then runs the neutral checks over the exported
STEP and prints one line per check.

The ``eval`` command runs a whole task set: it builds and scores every task
folder of the set, writes the results to a dated file and prints one line per
task and a summary of the run. With the ``--agent`` flag the agent writes the
candidate of every task first, and the same pipeline scores what it wrote.

The expected values of a part live in ``<project_dir>/expect/<part_id>.toml``.
They hold numbers only, so the same file judges a part whatever built it.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from aturb.config import ConfigError, active_pack, load_config, timeout_s
from aturb.contract.runner import Runner
from aturb.contract.types import BuildRequest, BuildResult
from aturb.packs import PackError, default_packs_root, load_runner
from aturb.verify.result import CheckResult

if TYPE_CHECKING:
    from aturb.agent.types import ModelClient
    from aturb.evals.result import TaskResult

EXPECT_DIR = "expect"
RESULTS_DIR_NAME = "results"
WORK_DIR_NAME = "tmp/agent"


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
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("tasks_dir")
    evaluate.add_argument("--config", default=None)
    evaluate.add_argument("--results-dir", default=None)
    evaluate.add_argument("--agent", action="store_true")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(Path(args.config) if args.config else None)
        name = active_pack(cfg)
        packs_root = default_packs_root()
        runner = load_runner(name, cfg, packs_root)
        if args.command == "eval":
            if args.agent:
                return _run_agent_eval(args, cfg, name, packs_root, runner,
                                       timeout_s(cfg))
            return _run_eval(args, runner, timeout_s(cfg))
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


def _run_eval(args: argparse.Namespace, runner: Runner, timeout: int) -> int:
    """Run a task set, write its results and print what happened.

    Every task folder of the set is built and scored, the results are written
    to a dated file and one line per task is printed, followed by a summary of
    the run. The summary score is the mean score of the tasks.

    The measuring library is imported here and not at the top of the file, so
    a plain build does not pay for loading it.
    """
    from aturb.evals.batch import run_batch
    from aturb.evals.report import write_results

    tasks_dir = Path(args.tasks_dir).resolve()
    results_dir = _results_dir(args, tasks_dir)
    try:
        results = run_batch(tasks_dir, runner, timeout)
    except OSError as exc:
        print(f"cannot read the task set {tasks_dir}: {exc}")
        return 2
    try:
        write_results(results_dir, results)
    except OSError as exc:
        print(f"cannot write the results in {results_dir}: {exc}")
        return 2
    return _report_results(results)


def _run_agent_eval(args: argparse.Namespace, cfg: dict, name: str,
                    packs_root: Path, runner: Runner, timeout: int) -> int:
    """Run the agent over a task set and score what it wrote.

    Every task folder of the set is copied into the scratch area, the agent
    writes one candidate there and the existing task runner builds and scores
    that candidate. The results go to the dated result file of the run and the
    agent runs go to the dated agent file next to it.

    The exit codes are the ones of the plain run: 0 when every task is ok, 1
    when any task is failed or error, and 2 for a configuration or pack error.
    """
    from aturb.agent.config import agent_settings
    from aturb.agent.record import write_agent_runs
    from aturb.agent.run import run_agent
    from aturb.agent.types import AgentError
    from aturb.evals.report import write_results
    from aturb.evals.runner import run_task
    from aturb.packs import discover

    settings = agent_settings(cfg)
    manifest = discover(packs_root)[name]
    try:
        client = _model_client(settings)
    except AgentError as exc:
        print(str(exc))
        return 2

    tasks_dir = Path(args.tasks_dir).resolve()
    results_dir = _results_dir(args, tasks_dir)
    work_dir = tasks_dir.parent / WORK_DIR_NAME
    try:
        folders = sorted(
            (path for path in tasks_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
    except OSError as exc:
        print(f"cannot read the task set {tasks_dir}: {exc}")
        return 2

    results = []
    runs = []
    for folder in folders:
        run = run_agent(folder, client, settings, manifest, work_dir)
        runs.append(run)
        results.append(run_task(work_dir / folder.name, runner, timeout))
    try:
        write_results(results_dir, results)
        write_agent_runs(results_dir, runs)
    except OSError as exc:
        print(f"cannot write the results in {results_dir}: {exc}")
        return 2
    return _report_results(results)


def _model_client(settings: dict) -> ModelClient:
    """Build the model client of the configuration.

    The provider, the model and the endpoint come from the configuration. The
    API key comes from the environment variable the configuration names, never
    from the configuration file itself.
    """
    from aturb.agent.config import read_api_key
    from aturb.agent.model import HttpModelClient

    key = read_api_key(settings)
    return HttpModelClient(
        base_url=settings["base_url"],
        model=settings["model"],
        api_key=key,
        timeout=float(settings["timeout_s"]),
        provider=settings["provider"],
    )


def _results_dir(args: argparse.Namespace, tasks_dir: Path) -> Path:
    """Return the folder the results of a run are written to."""
    if args.results_dir:
        return Path(args.results_dir).resolve()
    return tasks_dir.parent / RESULTS_DIR_NAME


def _report_results(results: list[TaskResult]) -> int:
    """Print one line per task and the summary of the run.

    The summary score is the mean score of the tasks. The exit code is 0 when
    every task is ok and 1 when any task is failed or error.
    """
    from aturb.evals.result import ERROR, FAILED, OK, set_score

    for result in results:
        print(f"task {result.task_id} {result.status} score={result.score}")
        if result.status in (FAILED, ERROR) and result.error:
            print(result.error)
    passed = sum(1 for result in results if result.status == OK)
    failed = sum(1 for result in results if result.status == FAILED)
    errored = sum(1 for result in results if result.status == ERROR)
    print(
        f"summary tasks={len(results)} passed={passed} failed={failed} "
        f"errored={errored} score={set_score(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
