"""Tests for the agent boundary types.

The boundary is pure data: a request, a response and the record of one agent
run. A run is checked when it is made, so a run that breaks the rules never
reaches a file.
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, fields
from typing import get_type_hints

import pytest

from aturb.agent.types import (
    ERROR,
    OK,
    AgentError,
    AgentRun,
    ModelClient,
    ModelRequest,
    ModelResponse,
)

FIELD_NAMES = (
    "task_id",
    "part_id",
    "provider",
    "model",
    "prompt_version",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "attempts",
    "status",
    "error",
)

COUNT_FIELDS = ("input_tokens", "output_tokens", "attempts")

TEXT_FIELDS = (
    "task_id",
    "part_id",
    "provider",
    "model",
    "prompt_version",
    "status",
    "error",
)


def _run(**overrides) -> AgentRun:
    """Return a valid ok run, with the given fields replaced."""
    values = {
        "task_id": "plate_2holes",
        "part_id": "plt0001",
        "provider": "openai_compatible",
        "model": "some-model-id",
        "prompt_version": "3f2a1c9d0e4b5a67",
        "input_tokens": 812,
        "output_tokens": 431,
        "cost_usd": 0.0041,
        "attempts": 1,
        "status": OK,
        "error": "",
    }
    values.update(overrides)
    return AgentRun(**values)


def test_a_valid_ok_run_is_accepted():
    """A run that did what it was asked is accepted."""
    run = _run()

    assert run.task_id == "plate_2holes"
    assert run.part_id == "plt0001"
    assert run.provider == "openai_compatible"
    assert run.model == "some-model-id"
    assert run.prompt_version == "3f2a1c9d0e4b5a67"
    assert run.input_tokens == 812
    assert run.output_tokens == 431
    assert run.cost_usd == pytest.approx(0.0041)
    assert run.attempts == 1
    assert run.status == OK
    assert run.error == ""


def test_a_valid_error_run_is_accepted():
    """A run that failed is accepted and keeps the text of the failure."""
    run = _run(status=ERROR, error="the call failed")

    assert run.status == ERROR
    assert run.error == "the call failed"


def test_an_error_run_may_have_an_empty_error_text():
    """An error run is not required to say why it failed."""
    run = _run(status=ERROR, error="")

    assert run.status == ERROR
    assert run.error == ""


def test_another_status_raises():
    """A status the model does not know is refused."""
    with pytest.raises(ValueError):
        _run(status="failed")


@pytest.mark.parametrize("field", COUNT_FIELDS)
def test_a_negative_count_raises(field):
    """A count below zero is refused."""
    with pytest.raises(ValueError):
        _run(**{field: -1})


def test_a_negative_cost_raises():
    """A cost below zero is refused."""
    with pytest.raises(ValueError):
        _run(cost_usd=-0.01)


@pytest.mark.parametrize("field", COUNT_FIELDS)
def test_a_non_numeric_count_raises(field):
    """A count that is not a number is refused."""
    with pytest.raises(ValueError):
        _run(**{field: "many"})


def test_a_non_numeric_cost_raises():
    """A cost that is not a number is refused."""
    with pytest.raises(ValueError):
        _run(cost_usd="free")


@pytest.mark.parametrize("field", COUNT_FIELDS)
def test_a_boolean_is_not_a_count(field):
    """A boolean is not a count, even though it is a whole number."""
    with pytest.raises(ValueError):
        _run(**{field: True})


def test_a_boolean_is_not_a_cost():
    """A boolean is not a cost, even though it is a number."""
    with pytest.raises(ValueError):
        _run(cost_usd=False)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_a_string_field_must_be_a_string(field):
    """A field that holds text must hold text."""
    with pytest.raises(ValueError):
        _run(**{field: 7})


def test_an_ok_run_must_not_carry_an_error_text():
    """A run that did what it was asked has nothing to report."""
    with pytest.raises(ValueError):
        _run(status=OK, error="the call failed")


def test_the_cost_is_normalized_to_a_float():
    """A cost given as a whole number becomes a float."""
    run = _run(cost_usd=0)

    assert isinstance(run.cost_usd, float)
    assert run.cost_usd == 0.0


def test_to_dict_returns_the_eleven_fields():
    """The dict holds the eleven fields of the run and nothing else."""
    run = _run()

    assert run.to_dict() == {
        "task_id": "plate_2holes",
        "part_id": "plt0001",
        "provider": "openai_compatible",
        "model": "some-model-id",
        "prompt_version": "3f2a1c9d0e4b5a67",
        "input_tokens": 812,
        "output_tokens": 431,
        "cost_usd": 0.0041,
        "attempts": 1,
        "status": "ok",
        "error": "",
    }


def test_the_fields_keep_their_order():
    """The eleven fields keep the order the record gives them."""
    run = _run()

    assert [field.name for field in fields(AgentRun)] == list(FIELD_NAMES)
    assert list(run.to_dict()) == list(FIELD_NAMES)
    assert len(run.to_dict()) == 11


def test_the_run_is_frozen():
    """A run cannot be changed once it is made."""
    run = _run()

    with pytest.raises(FrozenInstanceError):
        run.status = ERROR


def test_the_request_and_the_response_are_frozen():
    """The request and the response cannot be changed once they are made."""
    request = ModelRequest(
        prompt="build the part", model="some-model-id", max_output_tokens=8000)
    response = ModelResponse(
        text="the part", input_tokens=812, output_tokens=431)

    with pytest.raises(FrozenInstanceError):
        request.prompt = "build something else"
    with pytest.raises(FrozenInstanceError):
        response.text = "another part"


def test_the_model_client_has_one_method():
    """The protocol exposes exactly complete()."""
    public = {
        name
        for name, value in vars(ModelClient).items()
        if not name.startswith("_") and callable(value)
    }

    assert public == {"complete"}


def test_the_model_client_takes_a_request_and_returns_a_response():
    """The one method of the protocol is complete(request) -> ModelResponse."""
    signature = inspect.signature(ModelClient.complete)
    hints = get_type_hints(ModelClient.complete)
    parameters = [name for name in signature.parameters if name != "self"]

    assert parameters == ["request"]
    assert hints["request"] is ModelRequest
    assert hints["return"] is ModelResponse


def test_the_agent_error_is_an_exception():
    """The error of the agent boundary is an ordinary exception."""
    assert issubclass(AgentError, Exception)

    with pytest.raises(AgentError):
        raise AgentError("the call failed")
