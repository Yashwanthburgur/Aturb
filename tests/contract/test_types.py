"""Tests for the runner contract types."""

from __future__ import annotations

import json

import pytest

from aturb.contract import CONTRACT_VERSION
from aturb.contract.types import (
    BuildRequest,
    BuildResult,
    FailureKind,
    PackInfo,
)


def test_failure_kinds():
    assert {kind.value for kind in FailureKind} == {
        "rejected_unsafe",
        "syntax_error",
        "runtime_error",
        "timeout",
        "invalid_geometry",
        "export_failed",
        "runner_crash",
        "input_error",
    }


def test_build_request_round_trip():
    request = BuildRequest(
        project_root="C:/projects/demo",
        part_id="plt0001",
        language="python",
        outputs=("native", "step"),
        timeout_s=90,
    )

    assert BuildRequest.from_dict(request.to_dict()) == request


def test_build_request_json():
    request = BuildRequest(
        project_root="C:/projects/demo",
        part_id="plt0001",
        language="python",
    )

    loaded = json.loads(json.dumps(request.to_dict()))

    assert BuildRequest.from_dict(loaded) == request
    assert BuildRequest.from_dict(loaded).outputs == ("native", "step")


def test_build_result_ok_round_trip():
    result = BuildResult(
        status="ok",
        log_path="logs/plt0001.log",
        artifacts={"native": "out/plt0001.FCStd", "step": "out/plt0001.step"},
        native_diagnostics={"features": 3},
        duration_ms=1234,
    )

    restored = BuildResult.from_dict(result.to_dict())

    assert restored == result
    assert restored.failure_kind is None
    assert restored.contract_version == CONTRACT_VERSION


def test_build_result_failed_round_trip():
    result = BuildResult(
        status="failed",
        failure_kind=FailureKind.TIMEOUT,
        error_text="timed out after 60s",
        duration_ms=60000,
    )

    restored = BuildResult.from_dict(result.to_dict())

    assert restored == result
    assert restored.failure_kind is FailureKind.TIMEOUT
    assert result.to_dict()["failure_kind"] == "timeout"


def test_build_result_failed_requires_failure_kind():
    with pytest.raises(ValueError):
        BuildResult(status="failed")


def test_build_result_rejects_unknown_status():
    with pytest.raises(ValueError):
        BuildResult(status="maybe")


def test_pack_info_to_dict():
    info = PackInfo(name="example", language="python", version="0.1")

    assert info.to_dict() == {
        "name": "example",
        "language": "python",
        "version": "0.1",
    }
