"""Turn neutral check results into the score of a task.

The score of a task is the fraction of its required checks that passed,
scaled by the score a fully correct answer earns:

    max_score * passed_required_checks / total_required_checks

Only the checks named in ``answer.required_checks`` count. A required check
that the results do not hold counts as failed, and a check that is not
required is ignored.

This module knows nothing about builds. A build that failed, a missing STEP
file or an answer that could not be read is the runner's business and never
comes from here: this module only judges geometry, so a task is ``ok`` when
every required check passed and ``failed`` otherwise.
"""

from __future__ import annotations

from aturb.evals.answer import AnswerSpec
from aturb.evals.result import FAILED, OK
from aturb.verify.result import CheckResult


def score_task(answer: AnswerSpec, checks: list[CheckResult]) -> tuple[float, str]:
    """Return the score of a task and the text that says what did not pass.

    The score is ``max_score * passed / len(required_checks)``, where only the
    required checks count. A required check that is missing from the results
    counts as failed. The error text is empty when every required check
    passed, and names the checks that did not pass otherwise.
    """
    passed, failed = _judge(answer, checks)
    score = answer.max_score * passed / len(answer.required_checks)
    if not failed:
        return score, ""
    return score, f"the checks did not pass: {', '.join(failed)}"


def task_status(answer: AnswerSpec, checks: list[CheckResult]) -> str:
    """Return the status of a task from the results of its checks.

    A task is ``ok`` when every required check passed and ``failed``
    otherwise. A build that failed or an answer that could not be read is an
    ``error``, and that never comes from here.
    """
    _, failed = _judge(answer, checks)
    return OK if not failed else FAILED


def _judge(answer: AnswerSpec, checks: list[CheckResult]) -> tuple[int, list[str]]:
    """Return the required checks that passed and the names that did not.

    The results are looked up by name, so a check that is not required is
    ignored and a required check that the results do not hold counts as
    failed.
    """
    if not answer.required_checks:
        raise ValueError("the answer names no required check to score")
    results = {check.name: check for check in checks}
    passed = 0
    failed: list[str] = []
    for name in answer.required_checks:
        check = results.get(name)
        if check is not None and check.passed:
            passed += 1
        else:
            failed.append(name)
    return passed, failed
