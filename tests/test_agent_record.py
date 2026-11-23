"""Tests for the dated agent-run records.

The agent runs of one run go to one dated file with one record per run, so
they sit next to the result file of the same run. A record holds exactly the
eleven fields of an agent run and nothing else, and the runs survive the round
trip through the file.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from aturb.agent.attempts import (
    AttemptRecord,
    attempts_path,
    from_entry,
    read_attempts,
    write_attempts,
)
from aturb.agent.loop import AttemptEntry
from aturb.agent.record import read_agent_runs, write_agent_runs
from aturb.agent.types import ERROR, OK, AgentRun

FILE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_agent\.toml$")

FIELDS = {
    "task_id", "part_id", "provider", "model", "prompt_version",
    "input_tokens", "output_tokens", "cost_usd", "attempts", "status", "error",
}


def _runs() -> list[AgentRun]:
    """Two agent runs: one ok and one error."""
    return [
        AgentRun(
            task_id="plate_2holes",
            part_id="plt0001",
            provider="some-provider",
            model="some-model-id",
            prompt_version="3f2a1c9d0e4b5a67",
            input_tokens=812,
            output_tokens=431,
            cost_usd=0.0041,
            attempts=1,
            status=OK,
            error="",
        ),
        AgentRun(
            task_id="plate_4holes",
            part_id="plt0002",
            provider="some-provider",
            model="some-model-id",
            prompt_version="3f2a1c9d0e4b5a67",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            attempts=1,
            status=ERROR,
            error="the model call failed: the provider refused the call",
        ),
    ]


def _records(path: Path) -> list[dict]:
    """Read the records of a written agent-run file."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return raw["runs"]


def test_the_written_file_is_named_after_the_run(tmp_path):
    """The file sits in the results folder and carries the date and the time."""
    path = write_agent_runs(tmp_path, _runs())

    assert path.parent == tmp_path
    assert FILE_NAME.match(path.name)


def test_the_results_folder_is_made_when_it_is_missing(tmp_path):
    """The results folder is created when it is not there."""
    folder = tmp_path / "results"

    path = write_agent_runs(folder, _runs())

    assert path.parent == folder
    assert path.is_file()


def test_the_file_holds_one_record_per_run(tmp_path):
    """Every agent run has a record of its own, in the order of the runs."""
    runs = _runs()

    records = _records(write_agent_runs(tmp_path, runs))

    assert len(records) == len(runs)
    assert [record["task_id"] for record in records] == [
        "plate_2holes", "plate_4holes"]


def test_a_record_holds_the_eleven_fields(tmp_path):
    """A record holds the eleven fields of an agent run and nothing else."""
    records = _records(write_agent_runs(tmp_path, _runs()))

    assert set(records[0]) == FIELDS


def test_an_error_run_keeps_its_task_id_and_its_error_text(tmp_path):
    """An error run keeps its task ID and its error text in the file."""
    records = _records(write_agent_runs(tmp_path, _runs()))

    record = records[1]
    assert record["task_id"] == "plate_4holes"
    assert record["status"] == "error"
    assert record["attempts"] == 1
    assert record["error"] == "the model call failed: the provider refused the call"


def test_reading_the_file_back_gives_the_same_runs(tmp_path):
    """The agent runs of a run survive the round trip through the file."""
    runs = _runs()

    path = write_agent_runs(tmp_path, runs)

    assert read_agent_runs(path) == runs


def test_a_difficult_error_text_survives_the_round_trip(tmp_path):
    """Quotes, backslashes and newlines in an error text survive the file."""
    text = 'the model call failed: "timeout"\\path\nsecond line'
    runs = [AgentRun(
        task_id="plate_4holes",
        part_id="plt0002",
        provider="some-provider",
        model="some-model-id",
        prompt_version="3f2a1c9d0e4b5a67",
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        attempts=1,
        status=ERROR,
        error=text,
    )]

    path = write_agent_runs(tmp_path, runs)

    assert read_agent_runs(path) == runs


def test_a_record_with_a_missing_field_raises(tmp_path):
    """A record that does not hold the eleven fields is refused."""
    path = tmp_path / "runs.toml"
    path.write_text(
        "[[runs]]\n"
        'task_id = "plate_2holes"\n'
        'part_id = "plt0001"\n',
        encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        read_agent_runs(path)

    assert "missing" in str(excinfo.value)


def test_a_record_with_an_unknown_field_raises(tmp_path):
    """A record that holds more than the eleven fields is refused."""
    path = tmp_path / "runs.toml"
    path.write_text(
        "[[runs]]\n"
        'task_id = "plate_2holes"\n'
        'part_id = "plt0001"\n'
        'provider = "some-provider"\n'
        'model = "some-model-id"\n'
        'prompt_version = "3f2a1c9d0e4b5a67"\n'
        "input_tokens = 812\n"
        "output_tokens = 431\n"
        "cost_usd = 0.0041\n"
        "attempts = 1\n"
        'status = "ok"\n'
        'error = ""\n'
        'score = 1.0\n',
        encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        read_agent_runs(path)

    assert "unknown" in str(excinfo.value)


def test_a_file_that_is_not_valid_toml_raises(tmp_path):
    """A file that is not valid TOML is refused."""
    path = tmp_path / "runs.toml"
    path.write_text("this is not toml at all\n", encoding="utf-8")

    with pytest.raises(ValueError):
        read_agent_runs(path)


def test_a_run_with_no_agent_run_gives_a_file_with_no_record(tmp_path):
    """A run with no agent run writes a file that holds no record."""
    path = write_agent_runs(tmp_path, [])

    assert read_agent_runs(path) == []


def _attempts() -> list[AttemptRecord]:
    """Two attempts across tasks, with empty and non-empty failed checks."""
    return [
        AttemptRecord(
            task_id="plate_2holes", part_id="plt0001", attempt=1,
            prompt_version="first", input_tokens=100, output_tokens=20,
            cost_usd=0.001, status=OK, outcome="passed", score=1.0,
            failed_checks=(), error=""),
        AttemptRecord(
            task_id="plate_fillet", part_id="plt0002", attempt=2,
            prompt_version="second", input_tokens=200, output_tokens=40,
            cost_usd=0.0025, status="failed", outcome="checks_failed", score=0.6,
            failed_checks=("volume", "hole_count"),
            error='the checks did not pass: "volume"\\path\nsecond line\tand tab'),
    ]


def test_attempt_records_survive_the_round_trip(tmp_path):
    """Attempts share the agent stamp and preserve all twelve fields."""
    attempts = _attempts()
    agent_path = tmp_path / "2026-11-22_235959_agent.toml"

    path = write_attempts(attempts_path(agent_path), attempts)

    assert path.name == "2026-11-22_235959_attempts.toml"
    assert read_attempts(path) == attempts
    records = tomllib.loads(path.read_text(encoding="utf-8"))["attempts"]
    assert len(records) == 2
    assert set(records[0]) == {
        "task_id", "part_id", "attempt", "prompt_version", "input_tokens",
        "output_tokens", "cost_usd", "status", "outcome", "score",
        "failed_checks", "error",
    }
    assert records[0]["failed_checks"] == []
    assert records[1]["failed_checks"] == ["volume", "hole_count"]


def test_an_attempt_entry_converts_without_duplicate_mapping(tmp_path):
    """The loop entry converts directly, and an empty sequence round-trips."""
    expected = _attempts()[1]

    assert from_entry(AttemptEntry(**vars(expected))) == expected
    path = write_attempts(tmp_path / "empty_attempts.toml", [])
    assert read_attempts(path) == []
