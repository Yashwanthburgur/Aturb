"""One agent run: one task, one model call, one candidate file, one agent run.

The run is the whole agent path of one task. It reads the task file, the
requirement file and the prompt of the pack, composes the prompt, checks the
limits, calls the model once, strips the code fence of the answer and writes
the answer into the scratch project as the candidate of the part.

Every failure is a run with ``status = "error"`` and an error text, never an
exception: a missing requirement file, a missing pack prompt, a refused
budget, a failed call and an empty answer all end the same way. The run never
retries and never calls the model twice.

The run is CAD-neutral. The language of the part, the extension of the part
file and the prompt of the pack all come from the pack, so the core names no
CAD system and holds no prompt of its own.
"""

from __future__ import annotations

import math
from pathlib import Path

from aturb.agent.config import DEFAULTS
from aturb.agent.prompt import compose_prompt, prompt_version, strip_code_fence
from aturb.agent.types import ERROR, OK, AgentRun, ModelClient, ModelRequest
from aturb.agent.workspace import prepare_candidate_task, write_candidate
from aturb.evals.task import load_task
from aturb.packs import PackManifest

PROJECT_DIR_NAME = "project"
REQUIREMENTS_DIR_NAME = "requirements"
PROMPT_FILE_NAME = "agent.md"
REQUIREMENT_SUFFIX = ".md"

CHARS_PER_TOKEN = 4  # starting default
TOKENS_PER_MTOK = 1_000_000
ATTEMPTS = 1


def run_agent(
    task_dir: Path,
    client: ModelClient,
    settings: dict,
    pack: PackManifest,
    work_dir: Path,
) -> AgentRun:
    """Run the agent over one task and return the record of the run.

    The task folder is copied into the work directory, the prompt is composed
    from the task and from the pack, the model is called once and the answer
    is written into the scratch project as the candidate of the part.

    The limits are checked before the call: a prompt over the input token cap
    and a call that would pass the cost budget are refused without calling the
    model. Every failure is an error run, never an exception.
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
        max_input = _number(settings, "max_input_tokens")
        max_output = _number(settings, "max_output_tokens")
        max_cost = _number(settings, "max_cost_usd")
        input_price = _number(settings, "input_price_per_mtok")
        output_price = _number(settings, "output_price_per_mtok")
    except ValueError as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, "", str(exc))

    try:
        scratch = _scratch_task(task_dir, Path(work_dir), spec.task_id)
    except (OSError, ValueError) as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, "",
                          f"the scratch task folder could not be prepared: {exc}")
    try:
        requirement = _read_text(
            scratch / PROJECT_DIR_NAME / REQUIREMENTS_DIR_NAME
            / f"{spec.part_id}{REQUIREMENT_SUFFIX}",
            "the requirement file")
        pack_prompt = _read_text(
            pack.pack_dir / pack.prompt_dir / PROMPT_FILE_NAME,
            "the pack prompt")
        prompt = compose_prompt(pack_prompt, requirement)
    except ValueError as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, "", str(exc))

    estimated_input = estimate_input_tokens(prompt)
    if estimated_input > max_input:
        return _error_run(spec.task_id, spec.part_id, provider, model, "",
                          f"the prompt is over the input token cap: "
                          f"{estimated_input} tokens > {max_input:g}")
    estimated_cost = _cost(estimated_input, int(max_output),
                           input_price, output_price)
    if _has_price(input_price, output_price) and estimated_cost > max_cost:
        return _error_run(spec.task_id, spec.part_id, provider, model, "",
                          f"the call would pass the cost budget: "
                          f"{estimated_cost:.6f} USD > {max_cost:.6f} USD")

    version = prompt_version(prompt)
    request = ModelRequest(
        prompt=prompt,
        model=model,
        max_output_tokens=int(max_output),
    )
    try:
        response = client.complete(request)
    except Exception as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, version,
                          f"the model call failed: {exc}")

    text = strip_code_fence(response.text)
    if not text.strip():
        return _error_run(spec.task_id, spec.part_id, provider, model, version,
                          "the model returned an empty answer")
    try:
        write_candidate(scratch / PROJECT_DIR_NAME, spec.part_id,
                        pack.part_extension, text)
    except (OSError, ValueError) as exc:
        return _error_run(spec.task_id, spec.part_id, provider, model, version,
                          f"the candidate could not be written: {exc}")

    return AgentRun(
        task_id=spec.task_id,
        part_id=spec.part_id,
        provider=provider,
        model=model,
        prompt_version=version,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=_cost(response.input_tokens, response.output_tokens,
                       input_price, output_price),
        attempts=ATTEMPTS,
        status=OK,
        error="",
    )


def estimate_input_tokens(text: str) -> int:
    """Return the estimated number of input tokens of a prompt.

    The provider reports the real count after the call, but the cap is checked
    before the call, so the count is estimated from the length of the text.
    """
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _cost(input_tokens: int, output_tokens: int,
          input_price: float, output_price: float) -> float:
    """Return the cost of a call in dollars, from the configured prices."""
    return (input_tokens * input_price
            + output_tokens * output_price) / TOKENS_PER_MTOK


def _has_price(input_price: float, output_price: float) -> bool:
    """True when a price is configured for the tokens of a call."""
    return input_price > 0.0 or output_price > 0.0


def _scratch_task(task_dir: Path, work_dir: Path, task_id: str) -> Path:
    """Return the scratch task folder of one run.

    The committed task is copied into the work directory. A task folder that is
    already the scratch folder of that work directory is used as it is, so the
    caller may prepare the scratch folder itself.
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


def _error_run(task_id: str, part_id: str, provider: str, model: str,
               version: str, error: str) -> AgentRun:
    """Return the record of a run that failed."""
    return AgentRun(
        task_id=task_id,
        part_id=part_id,
        provider=provider,
        model=model,
        prompt_version=version,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        attempts=ATTEMPTS,
        status=ERROR,
        error=error,
    )
