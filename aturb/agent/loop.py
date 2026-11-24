"""The bounded repair loop of the agent.

The loop prepares the scratch task once and then repeats: one attempt of the
model, one judgement of the candidate, and either a stop or a repair prompt.
It is bounded by an attempt limit and by the cumulative token and cost
budgets. The loop never reads the expectation file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aturb.agent.config import DEFAULTS
from aturb.agent.conventions import check_conventions
from aturb.agent.feedback import BuildFeedback, feedback_text
from aturb.agent.prompt import compose_prompt
from aturb.agent.run import (
    AttemptOutcome,
    PreparationError,
    PreparedTask,
    compute_cost_usd,
    estimate_input_tokens,
    prepare_run,
    run_attempt,
)
from aturb.agent.types import ERROR, OK, AgentRun, ModelClient
from aturb.contract.runner import Runner
from aturb.contract.types import FailureKind
from aturb.evals.judge import TaskJudgement, judge_task
from aturb.evals.result import FAILED, TaskResult
from aturb.packs import PackManifest

DEFAULT_MAX_ATTEMPTS = 3  # starting default
DEFAULT_MAX_TOTAL_INPUT_TOKENS = 60_000  # starting default
DEFAULT_MAX_TOTAL_OUTPUT_TOKENS = 24_000  # starting default
DEFAULT_MAX_TOTAL_COST_USD = 0.75  # starting default
FAILED_CHECKS_PREFIX = "the checks did not pass: "

UNREPAIRABLE_FAILURE_KINDS = frozenset(
    {FailureKind.RUNNER_CRASH.value, FailureKind.INPUT_ERROR.value})

STOP_PASSED = "passed"
STOP_MAX_ATTEMPTS = "max_attempts"
STOP_BUDGET = "budget_exceeded"
STOP_UNREPAIRABLE = "unrepairable"
STOP_MODEL_ERROR = "model_error"
STOP_PREPARATION_ERROR = "preparation_error"
STOP_SETTINGS_ERROR = "settings_error"


@dataclass(frozen=True)
class AttemptEntry:
    """One attempt of the loop: a record for the operator, never a prompt."""

    task_id: str
    part_id: str
    attempt: int
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    status: str
    outcome: str
    score: float
    failed_checks: tuple[str, ...]
    error: str


@dataclass(frozen=True)
class LoopResult:
    """What one bounded loop did: the record, the last judgement, the attempts."""

    run: AgentRun
    result: TaskResult
    attempts: tuple[AttemptEntry, ...]
    stop_reason: str


@dataclass
class _Loop:
    """The bounds and the running totals of one bounded loop."""

    max_attempts: int
    max_total_input_tokens: int
    max_total_output_tokens: int
    max_total_cost_usd: float
    max_output: int
    input_price: float
    output_price: float
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    first_prompt_version: str = ""
    candidate_written: bool = False
    error: str = ""


def run_agent_loop(task_dir: Path, client: ModelClient, runner: Runner,
                   settings: dict, pack: PackManifest, work_dir: Path,
                   timeout_s: int) -> LoopResult:
    """Run the bounded repair loop over one task and return what it did.

    The scratch task is prepared once. Every attempt calls the model once and
    is judged by the evaluator. The loop stops on the first of: the candidate
    passes, the attempt limit is reached, the cumulative budget would be
    passed, the failure kind is not repairable, or the model call failed.
    """
    task_dir = Path(task_dir)
    provider = str(settings.get("provider", DEFAULTS.get("provider", "")))
    model = str(settings.get("model", DEFAULTS.get("model", "")))
    try:
        prepared = prepare_run(task_dir, pack, work_dir)
    except PreparationError as exc:
        task_id = exc.task_id or task_dir.name
        return _failed_loop(task_id, exc.part_id, provider, model, str(exc),
                            STOP_PREPARATION_ERROR)
    try:
        loop = _limits(settings)
    except ValueError as exc:
        return _failed_loop(prepared.task_id, prepared.part_id, provider, model,
                            str(exc), STOP_SETTINGS_ERROR)

    entries: list[AttemptEntry] = []
    feedback = ""
    last_result = TaskResult.from_error(
        prepared.task_id, prepared.part_id, "the loop made no attempt")
    stop_reason = STOP_MAX_ATTEMPTS
    for attempt in range(1, loop.max_attempts + 1):
        prompt = compose_prompt(prepared.pack_prompt,
                                prepared.requirement, feedback)
        refusal = _budget_refusal(prompt, loop)
        if refusal:
            loop.error = refusal
            entries.append(
                _entry(prepared, attempt, _empty(refusal), "budget_exceeded"))
            if not loop.candidate_written:
                last_result = TaskResult.from_error(
                    prepared.task_id, prepared.part_id, refusal)
            stop_reason = STOP_BUDGET
            break
        outcome = run_attempt(prepared, client, settings,
                              pack, feedback=feedback)
        _count(loop, outcome)
        if outcome.status != OK:
            loop.error = outcome.error
            name = "model_error" if outcome.prompt_version else "limit_refused"
            entries.append(_entry(prepared, attempt, outcome, name))
            if not loop.candidate_written:
                last_result = TaskResult.from_error(
                    prepared.task_id, prepared.part_id, outcome.error)
            stop_reason = STOP_MODEL_ERROR
            break
        loop.candidate_written = True
        judgement = judge_task(prepared.scratch, runner, timeout_s)
        last_result = judgement.result
        entries.append(_entry(prepared, attempt, outcome,
                       _outcome_name(judgement), judgement.result))
        if judgement.result.status == OK:
            stop_reason = STOP_PASSED
            break
        if attempt >= loop.max_attempts:
            stop_reason = STOP_MAX_ATTEMPTS
            break
        if judgement.failure_kind in UNREPAIRABLE_FAILURE_KINDS:
            stop_reason = STOP_UNREPAIRABLE
            break
        feedback = _repair_feedback(prepared, pack, outcome, judgement)

    status = OK if loop.candidate_written else ERROR
    run = AgentRun(
        task_id=prepared.task_id, part_id=prepared.part_id, provider=provider,
        model=model, prompt_version=loop.first_prompt_version,
        input_tokens=loop.input_tokens, output_tokens=loop.output_tokens,
        cost_usd=loop.cost_usd, attempts=loop.calls, status=status,
        error="" if status == OK else loop.error)
    return LoopResult(run=run, result=last_result, attempts=tuple(entries),
                      stop_reason=stop_reason)


def _failed_loop(task_id: str, part_id: str, provider: str, model: str,
                 error: str, stop_reason: str) -> LoopResult:
    """Return the result of a loop that stopped before any attempt."""
    run = AgentRun(
        task_id=task_id, part_id=part_id, provider=provider, model=model,
        prompt_version="", input_tokens=0, output_tokens=0, cost_usd=0.0,
        attempts=0, status=ERROR, error=error)
    return LoopResult(
        run=run, result=TaskResult.from_error(task_id, part_id, error),
        attempts=(), stop_reason=stop_reason)


def _limits(settings: dict) -> _Loop:
    """Return the bounds of one loop from the agent settings."""
    loop = _Loop(
        max_attempts=int(
            _number(settings, "max_attempts", DEFAULT_MAX_ATTEMPTS)),
        max_total_input_tokens=int(_number(
            settings, "max_total_input_tokens", DEFAULT_MAX_TOTAL_INPUT_TOKENS)),
        max_total_output_tokens=int(_number(
            settings, "max_total_output_tokens", DEFAULT_MAX_TOTAL_OUTPUT_TOKENS)),
        max_total_cost_usd=_number(
            settings, "max_total_cost_usd", DEFAULT_MAX_TOTAL_COST_USD),
        max_output=int(_number(settings, "max_output_tokens", 0)),
        input_price=_number(settings, "input_price_per_mtok", 0.0),
        output_price=_number(settings, "output_price_per_mtok", 0.0),
    )
    if loop.max_attempts < 1:
        raise ValueError("the agent setting 'max_attempts' must be at least 1")
    return loop


def _budget_refusal(prompt: str, loop: _Loop) -> str:
    """Return the error text when the cumulative budget would be passed."""
    estimated_input = estimate_input_tokens(prompt)
    if loop.input_tokens + estimated_input > loop.max_total_input_tokens:
        return (f"the cumulative input token budget would be passed: "
                f"{loop.input_tokens + estimated_input} tokens > {loop.max_total_input_tokens}")
    if loop.output_tokens + loop.max_output > loop.max_total_output_tokens:
        return (f"the cumulative output token budget would be passed: "
                f"{loop.output_tokens + loop.max_output} tokens > {loop.max_total_output_tokens}")
    if loop.input_price > 0.0 or loop.output_price > 0.0:
        estimated_cost = compute_cost_usd(
            estimated_input, loop.max_output, loop.input_price, loop.output_price)
        if loop.cost_usd + estimated_cost > loop.max_total_cost_usd:
            return (f"the cumulative cost budget would be passed: "
                    f"{loop.cost_usd + estimated_cost:.6f} USD > {loop.max_total_cost_usd:.6f} USD")
    return ""


def _count(loop: _Loop, outcome: AttemptOutcome) -> None:
    """Add the usage of one attempt to the running totals of the loop."""
    if outcome.prompt_version:
        loop.calls += 1
        loop.first_prompt_version = loop.first_prompt_version or outcome.prompt_version
    loop.input_tokens += outcome.input_tokens
    loop.output_tokens += outcome.output_tokens
    loop.cost_usd += outcome.cost_usd


def _repair_feedback(prepared: PreparedTask, pack: PackManifest,
                     outcome: AttemptOutcome, judgement: TaskJudgement) -> str:
    """Return the repair feedback of one attempt, from candidate-side inputs only."""
    build = BuildFeedback(
        status=judgement.build_status,
        failure_kind=judgement.failure_kind,
        error_text=judgement.error_text)
    conventions = check_conventions(
        prepared.part_id, pack.part_extension, outcome.candidate_text)
    return feedback_text(
        build, diagnostics=judgement.diagnostics, conventions=conventions,
        geometry=judgement.geometry, previous_code=outcome.candidate_text)


def _entry(prepared: PreparedTask, attempt: int, outcome: AttemptOutcome,
           name: str, result: TaskResult | None = None) -> AttemptEntry:
    """Return the entry of one attempt of the loop."""
    result = result or TaskResult.from_error(
        prepared.task_id, prepared.part_id, outcome.error)
    return AttemptEntry(
        task_id=prepared.task_id, part_id=prepared.part_id, attempt=attempt,
        prompt_version=outcome.prompt_version, input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens, cost_usd=outcome.cost_usd,
        status=result.status, outcome=name, score=result.score,
        failed_checks=_failed_checks(result), error=result.error)


def _empty(error: str) -> AttemptOutcome:
    """Return the outcome of an attempt that never called the model."""
    return AttemptOutcome(
        status=ERROR, prompt_version="", input_tokens=0, output_tokens=0,
        cost_usd=0.0, candidate_path=None, candidate_text="", error=error)


def _outcome_name(judgement: TaskJudgement) -> str:
    """Return the outcome of a judged attempt."""
    if judgement.result.status == OK:
        return "passed"
    if judgement.failure_kind:
        return f"build_failed:{judgement.failure_kind}"
    return "checks_failed" if judgement.result.status == FAILED else "judge_error"


def _failed_checks(result: TaskResult) -> tuple[str, ...]:
    """Return the names of the checks that did not pass, from the error text."""
    if not result.error.startswith(FAILED_CHECKS_PREFIX):
        return ()
    names = result.error[len(FAILED_CHECKS_PREFIX):]
    return tuple(name.strip() for name in names.split(",") if name.strip())


def _number(settings: dict, key: str, default: float) -> float:
    """Return one setting of the agent as a number."""
    value = settings.get(key, DEFAULTS.get(key, default))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the agent setting {key!r} must be a number")
    return float(value)
