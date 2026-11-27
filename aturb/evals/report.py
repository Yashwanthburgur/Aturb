"""Write the results of a run to a dated file, and read them back.

A run is written to one file named after the date and the time of the run, so
a later run can be compared with it. The file holds one ``[[results]]`` record
per task, in the order of the results, and every record holds exactly the five
fields of a result.

The project has no TOML writer, so the record is written here by hand. The
five fields are known and fixed, and the text of a field is escaped the way
TOML asks for it.
"""

from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path

from aturb.evals.result import TaskResult
from aturb.workspace.io import atomic_write_text

RECORD_KEYS = ("task_id", "part_id", "status", "score", "error")

FILE_NAME_FORMAT = "%Y-%m-%d_%H%M%S"

_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def write_results(results_dir: Path, results: list[TaskResult]) -> Path:
    """Write the results of a run to a dated file and return its path.

    The file is named ``<YYYY-MM-DD>_<HHMMSS>.toml`` and sits in
    ``results_dir``, which is made when it is not there. Every result has a
    record of its own, in the order of the results, and a record holds exactly
    the five fields of a result.
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{datetime.now().strftime(FILE_NAME_FORMAT)}.toml"
    blocks = [_record(result) for result in results]
    text = "\n\n".join(blocks)
    if text:
        text += "\n"
    atomic_write_text(path, text)
    return path


def read_results(path: Path) -> list[TaskResult]:
    """Read the results of a run from a dated file.

    The file holds one record per task, and every record is turned back into
    the result it was written from. A file that is not valid TOML, and a
    record that does not hold the five fields of a result, raise
    ``ValueError``.
    """
    path = Path(path)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in {path}: {exc}") from exc
    return [_result(record, path) for record in raw.get("results", [])]


def _record(result: TaskResult) -> str:
    """Return the TOML record of one result."""
    return "\n".join([
        "[[results]]",
        f"task_id = {_string(result.task_id)}",
        f"part_id = {_string(result.part_id)}",
        f"status = {_string(result.status)}",
        f"score = {float(result.score)!r}",
        f"error = {_string(result.error)}",
    ])


def _result(record: dict, path: Path) -> TaskResult:
    """Build one result from one record of a result file."""
    missing = [key for key in RECORD_KEYS if key not in record]
    if missing:
        raise ValueError(
            f"the result record in {path} is missing key(s): {', '.join(missing)}")
    unknown = sorted(set(record) - set(RECORD_KEYS))
    if unknown:
        raise ValueError(
            f"the result record in {path} has unknown key(s): {', '.join(unknown)}")
    return TaskResult(
        task_id=record["task_id"],
        part_id=record["part_id"],
        status=record["status"],
        score=record["score"],
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
