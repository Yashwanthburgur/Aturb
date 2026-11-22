"""One agent run: one task, one model call, one candidate file, one agent run.

The run is made of three pieces that the bounded loop of the next phase
reuses: the preparation of the task, one attempt of the model and the record
of the run. Every failure is a run with ``status = "error"`` and an error
text, never an exception, and the run never calls the model twice. The run is
CAD-neutral: the part language, the part extension and the pack prompt all
come from the pack.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from aturb.agent.config import DEFAULTS
from aturb.agent.prompt import compose_prompt, prompt_version, strip_code_fence
from aturb.agent.types import ERROR, OK, AgentRun, ModelClient, ModelRequest
from aturb.agent.workspace import prepare_candidate_task, write_candidate
from aturb.evals.task import TaskSpec, load_task
from aturb.packs import PackManifest

PROJECT_DIR_NAME = "project"
REQUIREMENTS_DIR_NAME = "requirements"
PROMPT_FILE_NAME = "agent.md"
REQUIREMENT_SUFFIX = ".md"

CHARS_PER_TOKEN = 4  # starting default
TOKENS_PER_MTOK = 1_000_000
ATTEMPTS = 1


@dataclass(frozen=True)
class PreparedTask:
    """One task prepared for a run: the scratch folder and the texts of the prompt."""

    task_id: str
    part_id: str
    scratch: Path
    requirement: str
    pack_prompt: str


@dataclass(frozen=True)
class AttemptOutcome:
    """The outcome of one attempt: what the model answered and what it cost."""

    status: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    candidate_path: Path | None
    candidate_text: str
    error: str


class PreparationError(ValueError):
    """The task could not be prepared for a run.

    The message is the error text of the run and the names are the task and
    the part that could not be prepared.
    """

    def __init__(self, message: str, task_id: str = "", part_id: str = "") -> None:
        """Take the error text and the names of the task."""
        super().__init__(message)
        self.task_id = task_id
        self.part_id = part_id


def run_agent(
    task_dir: Path,
    client: ModelClient,
    settings: dict,
    pack: PackManifest,
    work_dir: Path,
) -> AgentRun:
    """Run the agent over one task and return the record of the run.

    The task folder is copied into the work directory, the model is called
    once and the answer is written into the scratch project as the candidate
    of the part. The limits are checked before the call and every failure is
    an error run.
    """
    task_dir = Path(task_dir)
    provider = _setting(settings, "provider")
    model = _setting(settings, "model")
    try:
        spec = load_task(task_dir)
    except (OSError, ValueError) as exc:
        return _error_run(task_dir.name, "", provider, model, "",
                          f"the task file could not be read: {exc}")
    try:
        _limits(settings)
    except ValueError as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, "", str(exc))
    try:
        prepared = prepare_run(task_dir, pack, work_dir, spec)
    except PreparationError as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, "", str(exc))

    outcome = run_attempt(prepared, client, settings, pack)
    return build_run(prepared, outcome, settings)


def prepare_run(
    task_dir: Path,
    pack: PackManifest,
    work_dir: Path,
    spec: TaskSpec | None = None,
) -> PreparedTask:
    """Prepare one task for a run and return what an attempt needs.

    The task folder is copied into the work directory, the requirement file and
    the prompt of the pack are read. The expectation file is never read. The
    task file is read here when the spec is not given.
    """
    task_dir = Path(task_dir)
    if spec is None:
        try:
            spec = load_task(task_dir)
        except (OSError, ValueError) as exc:
            raise PreparationError(
                f"the task file could not be read: {exc}") from exc
    try:
        scratch = _scratch_task(task_dir, Path(work_dir), spec.task_id)
    except (OSError, ValueError) as exc:
        raise PreparationError(
            f"the scratch task folder could not be prepared: {exc}",
            spec.task_id, spec.part_id) from exc
    try:
        requirement = _read_text(
            scratch / PROJECT_DIR_NAME / REQUIREMENTS_DIR_NAME
            / f"{spec.part_id}{REQUIREMENT_SUFFIX}",
            "the requirement file")
        pack_prompt = _read_text(
            pack.pack_dir / pack.prompt_dir / PROMPT_FILE_NAME,
            "the pack prompt")
    except ValueError as exc:
        raise PreparationError(str(exc), spec.task_id, spec.part_id) from exc
    return PreparedTask(
        task_id=spec.task_id, part_id=spec.part_id, scratch=scratch,
        requirement=requirement, pack_prompt=pack_prompt)


def run_attempt(
    prepared: PreparedTask,
    client: ModelClient,
    settings: dict,
    pack: PackManifest,
    feedback: str = "",
) -> AttemptOutcome:
    """Run one attempt of the model over a prepared task.

    The prompt is composed from the pack prompt, the requirement and the
    optional feedback, and the answer is written into the scratch project.
    """
    model = _setting(settings, "model")
    try:
        max_input, max_output, max_cost, input_price, output_price = _limits(
            settings)
    except ValueError as exc:
        return _failed_attempt("", str(exc))

    prompt = compose_prompt(prepared.pack_prompt,
                            prepared.requirement, feedback)
    estimated_input = estimate_input_tokens(prompt)
    if estimated_input > max_input:
        return _failed_attempt("", f"the prompt is over the input token cap: "
                               f"{estimated_input} tokens > {max_input:g}")
    estimated_cost = compute_cost_usd(estimated_input, int(max_output),
                                      input_price, output_price)
    if _has_price(input_price, output_price) and estimated_cost > max_cost:
        return _failed_attempt("", f"the call would pass the cost budget: "
                               f"{estimated_cost:.6f} USD > {max_cost:.6f} USD")

    version = prompt_version(prompt)
    request = ModelRequest(prompt=prompt, model=model,
                           max_output_tokens=int(max_output))
    try:
        response = client.complete(request)
    except Exception as exc:
        return _failed_attempt(version, f"the model call failed: {exc}")

    text = strip_code_fence(response.text)
    if not text.strip():
        return _failed_attempt(version, "the model returned an empty answer")
    try:
        path = write_candidate(prepared.scratch / PROJECT_DIR_NAME, prepared.part_id,
                               pack.part_extension, text)
    except (OSError, ValueError) as exc:
        return _failed_attempt(version, f"the candidate could not be written: {exc}")

    cost = compute_cost_usd(response.input_tokens, response.output_tokens,
                            input_price, output_price)
    return AttemptOutcome(
        status=OK, prompt_version=version, input_tokens=response.input_tokens,
        output_tokens=response.output_tokens, cost_usd=cost,
        candidate_path=path, candidate_text=text, error="")


def build_run(
    prepared: PreparedTask,
    outcome: AttemptOutcome,
    settings: dict,
    attempts: int = ATTEMPTS,
) -> AgentRun:
    """Return the record of a run from the outcome of its attempt."""
    return AgentRun(
        task_id=prepared.task_id, part_id=prepared.part_id,
        provider=_setting(settings, "provider"), model=_setting(settings, "model"),
        prompt_version=outcome.prompt_version, input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens, cost_usd=outcome.cost_usd,
        attempts=attempts, status=outcome.status, error=outcome.error)


def estimate_input_tokens(text: str) -> int:
    """Return the estimated number of input tokens of a prompt."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def compute_cost_usd(input_tokens: int, output_tokens: int,
                     input_price: float, output_price: float) -> float:
    """Return the cost of a call in dollars, from the configured prices."""
    return (input_tokens * input_price
            + output_tokens * output_price) / TOKENS_PER_MTOK


def _limits(settings: dict) -> tuple[float, float, float, float, float]:
    """Return the caps and the prices of the agent settings."""
    return (_number(settings, "max_input_tokens"),
            _number(settings, "max_output_tokens"),
            _number(settings, "max_cost_usd"),
            _number(settings, "input_price_per_mtok"),
            _number(settings, "output_price_per_mtok"))


def _has_price(input_price: float, output_price: float) -> bool:
    """True when a price is configured for the tokens of a call."""
    return input_price > 0.0 or output_price > 0.0


def _scratch_task(task_dir: Path, work_dir: Path, task_id: str) -> Path:
    """Return the scratch task folder of one run.

    The committed task is copied into the work directory, unless the task
    folder is already the scratch folder of that work directory.
    """
    scratch = (work_dir / task_id).resolve()
    if task_dir.resolve() == scratch:
        return scratch
    return prepare_candidate_task(task_dir, work_dir)


def _read_text(path: Path, label: str) -> str:
    """Return the text of a file, or raise ValueError with the reason."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label} could not be read: {exc}") from exc


def _setting(settings: dict, key: str) -> str:
    """Return one setting of the agent as text."""
    value = settings.get(key, DEFAULTS.get(key, ""))
    return value if isinstance(value, str) else str(value)


def _number(settings: dict, key: str) -> float:
    """Return one setting of the agent as a number."""
    value = settings.get(key, DEFAULTS.get(key, 0))
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the agent setting {key!r} must be a number")
    return float(value)


def _failed_attempt(version: str, error: str) -> AttemptOutcome:
    """Return the outcome of an attempt that failed."""
    return AttemptOutcome(
        status=ERROR, prompt_version=version, input_tokens=0, output_tokens=0,
        cost_usd=0.0, candidate_path=None, candidate_text="", error=error)


def _error_run(task_id: str, part_id: str, provider: str, model: str,
               version: str, error: str) -> AgentRun:
    """Return the record of a run that failed."""
    return AgentRun(
        task_id=task_id, part_id=part_id, provider=provider, model=model,
        prompt_version=version, input_tokens=0, output_tokens=0, cost_usd=0.0,
        attempts=ATTEMPTS, status=ERROR, error=error)
