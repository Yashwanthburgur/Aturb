"""One result type for one task, so a batch result is a list of the same thing.

A task has three outcomes:

- ``ok``: the build succeeded and every required check passed.
- ``failed``: the build succeeded but at least one required check failed.
- ``error``: the task could not be judged at all: the build failed, the STEP
  file is missing, or the answer could not be read.

The score is the score of the task, from 0.0 upward. The rule that turns check
results into that score belongs to the scoring layer, not to this type: this
type only carries the outcome, the score and the error text.

The type holds no geometry and no CAD concept. It holds the identity of the
task, the outcome, the score and the error text.
"""

from __future__ import annotations

from dataclasses import dataclass

OK = "ok"
FAILED = "failed"
ERROR = "error"

STATUSES = (OK, FAILED, ERROR)


@dataclass(frozen=True)
class TaskResult:
    """The outcome of one task.

    ``part_id`` is the empty string when the task file could not be read, so
    the part is only named when the task file was read. ``error`` is empty
    when the task passed and says what went wrong otherwise.
    """

    task_id: str
    part_id: str
    status: str
    score: float
    error: str = ""

    def __post_init__(self) -> None:
        """Check that the result is one the model allows."""
        if self.status not in STATUSES:
            raise ValueError(
                f"status must be one of {', '.join(STATUSES)}, "
                f"got {self.status!r}")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ValueError("the score must be a number")
        if self.score < 0.0:
            raise ValueError(
                f"the score cannot be negative, got {self.score!r}")
        if not isinstance(self.error, str):
            raise ValueError("the error must be a string")
        # The score is a number of points, so it is always a float.
        object.__setattr__(self, "score", float(self.score))
        if self.status == OK and self.error:
            raise ValueError("an ok task must not carry an error text")

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this result."""
        return {
            "task_id": self.task_id,
            "part_id": self.part_id,
            "status": self.status,
            "score": self.score,
            "error": self.error,
        }

    @classmethod
    def from_error(cls, task_id: str, part_id: str, error: str) -> "TaskResult":
        """Build the result of a task that could not be judged.

        The build failed, the STEP file is missing, or the answer could not be
        read. The error text says which of them it was.
        """
        return cls(task_id=task_id, part_id=part_id, status=ERROR, score=0.0,
                   error=error)


def set_score(results: list[TaskResult]) -> float:
    """Return the score of a task set: the mean score of its tasks."""
    if not results:
        return 0.0
    return sum(result.score for result in results) / len(results)


def passed_count(results: list[TaskResult]) -> int:
    """Return the number of tasks that passed in a task set."""
    return sum(1 for result in results if result.status == OK)
