"""The types the agent boundary is made of.

The boundary is pure data: a request that goes to the model, a response that
comes back, and the record of one agent run. Nothing here reads a file, opens
a socket or names a CAD system.

The agent run is a record of its own, separate from the task result of the
evaluation. The task result says what the geometry scored; the agent run says
what the agent did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

OK = "ok"
ERROR = "error"

STATUSES = (OK, ERROR)


class AgentError(Exception):
    """Raised when the agent boundary cannot do what it was asked to do."""


@dataclass(frozen=True)
class ModelRequest:
    """The request that goes to the model.

    ``prompt`` is the exact text that is sent, ``model`` is the model
    identifier sent with it, and ``max_output_tokens`` is the cap on the
    answer.
    """

    prompt: str
    model: str
    max_output_tokens: int


@dataclass(frozen=True)
class ModelResponse:
    """The response that comes back from the model.

    ``text`` is the answer, and the two token counts are the ones the provider
    reported.
    """

    text: str
    input_tokens: int
    output_tokens: int


class ModelClient(Protocol):
    """A client that turns one request into one response."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Send one request to the model and return its response."""
        ...


@dataclass(frozen=True)
class AgentRun:
    """The record of one agent run.

    The run says what the agent did, not what the geometry scored: ``status``
    is ``ok`` or ``error`` about the agent, and the geometry status is the one
    of the task result. ``error`` is empty when the run is ``ok`` and may be
    empty when the run is ``error``.
    """

    task_id: str
    part_id: str
    provider: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    attempts: int
    status: str
    error: str

    def __post_init__(self) -> None:
        """Check that the run is one the model allows."""
        _text(self.task_id, "task_id")
        _text(self.part_id, "part_id")
        _text(self.provider, "provider")
        _text(self.model, "model")
        _text(self.prompt_version, "prompt_version")
        _text(self.status, "status")
        _text(self.error, "error")
        _count(self.input_tokens, "input_tokens")
        _count(self.output_tokens, "output_tokens")
        _count(self.attempts, "attempts")
        cost = _number(self.cost_usd, "cost_usd")
        if self.status not in STATUSES:
            raise ValueError(
                f"status must be one of {', '.join(STATUSES)}, "
                f"got {self.status!r}")
        if self.status == OK and self.error:
            raise ValueError("an ok agent run must not carry an error text")
        # The cost is a number of dollars, so it is always a float.
        object.__setattr__(self, "cost_usd", float(cost))

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this run."""
        return {
            "task_id": self.task_id,
            "part_id": self.part_id,
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "attempts": self.attempts,
            "status": self.status,
            "error": self.error,
        }


def _text(value, key: str) -> None:
    """Raise when a value is not text."""
    if not isinstance(value, str):
        raise ValueError(f"the {key} must be a string")


def _count(value, key: str) -> None:
    """Raise when a value is not a non-negative whole number."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"the {key} must be a whole number")
    if value < 0:
        raise ValueError(f"the {key} cannot be negative, got {value!r}")


def _number(value, key: str) -> float:
    """Return a value as a non-negative number, or raise when it is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"the {key} must be a number")
    if value < 0:
        raise ValueError(f"the {key} cannot be negative, got {value!r}")
    return float(value)
