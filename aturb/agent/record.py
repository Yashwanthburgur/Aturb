"""Write the agent runs of a run to a dated file, and read them back.

The agent runs of one run go to one file of their own, named after the date
and the time of the run, so they sit next to the result file of the same run
and a later run can be compared with them. The file holds one ``[[runs]]``
record per agent run, in the order of the runs, and every record holds exactly
the eleven fields of an agent run.

The agent run is a record of its own: the Phase 4 result record says what the
geometry scored and stays frozen at five fields, while this file says what the
agent did. Neither grows.

The project has no TOML writer, so the record is written here by hand. The
eleven fields are known and fixed, and the text of a field is escaped the way
TOML asks for it. The escaper of the Phase 4 result file is repeated here
rather than shared, because that module is frozen and is not changed.
"""

from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path

from aturb.agent.types import AgentRun

RECORD_KEYS = ("task_id", "part_id", "provider", "model", "prompt_version",
               "input_tokens", "output_tokens", "cost_usd", "attempts",
               "status", "error")

FILE_NAME_FORMAT = "%Y-%m-%d_%H%M%S"
FILE_SUFFIX = "_agent.toml"

_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def write_agent_runs(results_dir: Path, runs: list[AgentRun]) -> Path:
    """Write the agent runs of a run to a dated file and return its path.

    The file is named ``<YYYY-MM-DD>_<HHMMSS>_agent.toml`` and sits in
    ``results_dir``, which is made when it is not there. Every agent run has a
    record of its own, in the order of the runs, and a record holds exactly the
    eleven fields of an agent run.
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.now().strftime(FILE_NAME_FORMAT)
    path = results_dir / f"{name}{FILE_SUFFIX}"
    blocks = [_record(run) for run in runs]
    text = "\n\n".join(blocks)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")
    return path


def read_agent_runs(path: Path) -> list[AgentRun]:
    """Read the agent runs of a run from a dated file.

    The file holds one record per agent run, and every record is turned back
    into the agent run it was written from. A file that is not valid TOML, and
    a record that does not hold the eleven fields of an agent run, raise
    ``ValueError``.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return [_run(record, path) for record in raw.get("runs", [])]


def _record(run: AgentRun) -> str:
    """Return the TOML record of one agent run."""
    return "\n".join([
        "[[runs]]",
        f"task_id = {_string(run.task_id)}",
        f"part_id = {_string(run.part_id)}",
        f"provider = {_string(run.provider)}",
        f"model = {_string(run.model)}",
        f"prompt_version = {_string(run.prompt_version)}",
        f"input_tokens = {int(run.input_tokens)}",
        f"output_tokens = {int(run.output_tokens)}",
        f"cost_usd = {float(run.cost_usd)!r}",
        f"attempts = {int(run.attempts)}",
        f"status = {_string(run.status)}",
        f"error = {_string(run.error)}",
    ])


def _run(record: dict, path: Path) -> AgentRun:
    """Build one agent run from one record of an agent-run file."""
    missing = [key for key in RECORD_KEYS if key not in record]
    if missing:
        raise ValueError(
            f"the agent run record in {path} is missing key(s): "
            f"{', '.join(missing)}")
    unknown = sorted(set(record) - set(RECORD_KEYS))
    if unknown:
        raise ValueError(
            f"the agent run record in {path} has unknown key(s): "
            f"{', '.join(unknown)}")
    return AgentRun(
        task_id=record["task_id"],
        part_id=record["part_id"],
        provider=record["provider"],
        model=record["model"],
        prompt_version=record["prompt_version"],
        input_tokens=record["input_tokens"],
        output_tokens=record["output_tokens"],
        cost_usd=record["cost_usd"],
        attempts=record["attempts"],
        status=record["status"],
        error=record["error"],
    )


def _string(value: str) -> str:
    """Return a TOML basic string for a text."""
    parts = []
    for char in value:
        if char in _ESCAPES:
            parts.append(_ESCAPES[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            parts.append(f"\\u{ord(char):04X}")
        else:
            parts.append(char)
    return '"' + "".join(parts) + '"'
