"""Write the operator-facing record of every attempt, and read it back.

The attempts file sits beside the agent-run file and shares its timestamp. It
is an operator record only: the agent path never reads it and never sends it
to a model. The writer is hand-written TOML, like the agent-run record writer.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from aturb.agent.record import FILE_SUFFIX as AGENT_FILE_SUFFIX
from aturb.agent.record import toml_string

ATTEMPT_KEYS = (
    "task_id", "part_id", "attempt", "prompt_version", "input_tokens",
    "output_tokens", "cost_usd", "status", "outcome", "score",
    "failed_checks", "error",
)
ATTEMPT_FILE_SUFFIX = "_attempts.toml"


@dataclass(frozen=True)
class AttemptRecord:
    """The twelve operator-facing fields of one attempt."""

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


def from_entry(entry) -> AttemptRecord:
    """Convert an AttemptEntry or a duck-typed equivalent to its record."""
    return AttemptRecord(
        task_id=entry.task_id,
        part_id=entry.part_id,
        attempt=entry.attempt,
        prompt_version=entry.prompt_version,
        input_tokens=entry.input_tokens,
        output_tokens=entry.output_tokens,
        cost_usd=entry.cost_usd,
        status=entry.status,
        outcome=entry.outcome,
        score=entry.score,
        failed_checks=tuple(entry.failed_checks),
        error=entry.error,
    )


def attempts_path(agent_path: Path) -> Path:
    """Return the attempts path with exactly the agent file's timestamp."""
    agent_path = Path(agent_path)
    if not agent_path.name.endswith(AGENT_FILE_SUFFIX):
        raise ValueError(f"not an agent-run record path: {agent_path}")
    stamp = agent_path.name[:-len(AGENT_FILE_SUFFIX)]
    return agent_path.with_name(f"{stamp}{ATTEMPT_FILE_SUFFIX}")


def write_attempts(path: Path, attempts: Sequence[AttemptRecord]) -> Path:
    """Write one ``[[attempts]]`` block per attempt and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n\n".join(_record(attempt) for attempt in attempts)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def read_attempts(path: Path) -> list[AttemptRecord]:
    """Read and validate every attempt record in an attempts file."""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return [_attempt(record, path) for record in raw.get("attempts", [])]


def _record(attempt: AttemptRecord) -> str:
    """Return the TOML block of one attempt."""
    checks = ", ".join(toml_string(name) for name in attempt.failed_checks)
    return "\n".join([
        "[[attempts]]",
        f"task_id = {toml_string(attempt.task_id)}",
        f"part_id = {toml_string(attempt.part_id)}",
        f"attempt = {int(attempt.attempt)}",
        f"prompt_version = {toml_string(attempt.prompt_version)}",
        f"input_tokens = {int(attempt.input_tokens)}",
        f"output_tokens = {int(attempt.output_tokens)}",
        f"cost_usd = {float(attempt.cost_usd)!r}",
        f"status = {toml_string(attempt.status)}",
        f"outcome = {toml_string(attempt.outcome)}",
        f"score = {float(attempt.score)!r}",
        f"failed_checks = [{checks}]",
        f"error = {toml_string(attempt.error)}",
    ])


def _attempt(record: dict, path: Path) -> AttemptRecord:
    """Build one attempt from a record, refusing missing or unknown keys."""
    missing = [key for key in ATTEMPT_KEYS if key not in record]
    if missing:
        raise ValueError(
            f"the attempt record in {path} is missing key(s): {', '.join(missing)}")
    unknown = sorted(set(record) - set(ATTEMPT_KEYS))
    if unknown:
        raise ValueError(
            f"the attempt record in {path} has unknown key(s): {', '.join(unknown)}")
    return AttemptRecord(
        task_id=record["task_id"],
        part_id=record["part_id"],
        attempt=record["attempt"],
        prompt_version=record["prompt_version"],
        input_tokens=record["input_tokens"],
        output_tokens=record["output_tokens"],
        cost_usd=record["cost_usd"],
        status=record["status"],
        outcome=record["outcome"],
        score=record["score"],
        failed_checks=tuple(record["failed_checks"]),
        error=record["error"],
    )
