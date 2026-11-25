"""Tests for the generation command handler, manifest and report."""

from __future__ import annotations

import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from aturb.agent import generate_cli
from aturb.agent.generate import GenerateResult
from aturb.agent.generate_cli import (
    format_generate_report,
    run_generate_command,
    write_generate_manifest,
)
from aturb.agent.types import AgentError
from aturb.evals.judge import CandidateGeometry, HoleSummary

PART_ID = "part0001"


def _result(workspace: Path, *, ok: bool = True) -> GenerateResult:
    workspace = workspace.resolve()
    part = workspace / "project" / "parts" / f"{PART_ID}_candidate.stub"
    step = workspace / "project" / "out" / PART_ID / f"{PART_ID}.step"
    native = workspace / "project" / "out" / PART_ID / f"{PART_ID}.stubnative"
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_text("# candidate\n", encoding="utf-8")
    geometry = CandidateGeometry(
        is_valid=True, is_single_solid=True, volume=29698.407105255385,
        bbox_size=(100.0, 50.0, 6.0),
        holes=(HoleSummary(diameter=8.0, x=0.0, y=0.0),))
    if ok:
        step.parent.mkdir(parents=True, exist_ok=True)
        step.write_text("STEP", encoding="utf-8")
        native.write_text("native", encoding="utf-8")
    return GenerateResult(
        status="ok" if ok else "error", part_id=PART_ID, workspace=workspace,
        part_path=part, step_path=step if ok else None,
        native_path=native if ok else None,
        build_status="ok" if ok else "failed",
        failure_kind="" if ok else "syntax_error",
        geometry=geometry if ok else None,
        conventions=("C2: advisory finding",) if ok else (),
        attempts=2, input_tokens=200, output_tokens=100, cost_usd=0.0004,
        prompt_version="0123456789abcdef",
        stop_reason="built" if ok else "max_attempts",
        error="" if ok else r"bad C:\work\part.stub")


def _args(tmp_path: Path, **overrides):
    values = dict(
        prompt="Build a plate", prompt_file=None, out=tmp_path / "generated",
        part_id=PART_ID, max_attempts=None, pack=None)
    values.update(overrides)
    return SimpleNamespace(**values)


def _cfg() -> dict:
    return {
        "active_pack": "stub", "timeouts": {"build_s": 60},
        "agent": {"model": "fake-model"},
    }


def _fake_generate(monkeypatch, calls: dict, *, ok: bool = True):
    def fake(requirement, out_dir, client, runner, settings, pack, timeout_s,
             part_id):
        calls.update(requirement=requirement, out_dir=out_dir, settings=settings,
                     timeout_s=timeout_s, part_id=part_id, pack=pack.name)
        return _result(Path(out_dir), ok=ok)

    monkeypatch.setattr(generate_cli, "generate_part", fake)


def test_manifest_is_parseable_and_uses_relative_paths(tmp_path):
    result = _result(tmp_path)
    path = write_generate_manifest(result)
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert data["status"] == "ok" and data["attempts"] == 2
    assert data["part_file"] == "project/parts/part0001_candidate.stub"
    assert data["step_file"] == "project/out/part0001/part0001.step"
    assert data["native_file"] == "project/out/part0001/part0001.stubnative"
    for key in ("part_file", "step_file", "native_file"):
        assert not data[key].startswith(("/", "\\"))
        assert ":\\" not in data[key] and ":/" not in data[key]
    assert data["is_valid"] is True and data["is_single_solid"] is True
    assert data["volume"] == pytest.approx(29698.407105255385)
    assert data["bbox_size"] == [100.0, 50.0, 6.0]
    assert data["hole_count"] == 1
    assert data["holes"] == [{"diameter": 8.0, "x": 0.0, "y": 0.0}]
    assert data["conventions"] == ["C2: advisory finding"]


def test_manifest_handles_a_failed_build_and_sanitizes_error(tmp_path):
    path = write_generate_manifest(_result(tmp_path, ok=False))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert data["failure_kind"] == "syntax_error"
    assert data["step_file"] == "" and data["native_file"] == ""
    assert "is_valid" not in data and "holes" not in data
    assert "C:\\" not in data["error"]
    assert data["error"].endswith("part.stub")


def test_report_renders_geometry_holes_conventions_and_errors(tmp_path):
    report = format_generate_report(_result(tmp_path))
    for text in (
            "Status: ok", "Stop reason: built", "Attempts: 2",
            "source: project/parts/part0001_candidate.stub",
            "manifest: result.toml", "is_valid: true", "is_single_solid: true",
            "volume: 29698.407105 mm^3", "bbox_size: 100 x 50 x 6 mm",
            "holes: 1", "diameter 8 mm", "C2: advisory finding"):
        assert text in report
    failed = format_generate_report(_result(tmp_path / "failed", ok=False))
    assert "Failure kind: syntax_error" in failed
    assert "Error:" in failed and "part.stub" in failed
    error_line = next(line for line in failed.splitlines()
                      if line.startswith("Error:"))
    assert "C:\\" not in error_line


def test_report_prints_the_workspace_relative_when_it_is_inside_the_current(
        tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "evals" / "tmp" / "generate" / "2026-11-25_095531"
    report = format_generate_report(_result(workspace))
    assert "Workspace: evals/tmp/generate/2026-11-25_095531" in report
    assert str(tmp_path) not in report


def test_report_prints_the_workspace_as_it_is_when_it_is_outside_the_current(
        tmp_path, monkeypatch):
    current = tmp_path / "current"
    current.mkdir()
    monkeypatch.chdir(current)
    workspace = tmp_path / "outside"
    report = format_generate_report(_result(workspace))
    assert f"Workspace: {workspace.resolve()}" in report


def test_the_manifest_of_a_workspace_outside_the_current_has_no_absolute_path(
        tmp_path, monkeypatch):
    current = tmp_path / "current"
    current.mkdir()
    monkeypatch.chdir(current)
    workspace = tmp_path / "outside"
    path = write_generate_manifest(_result(workspace))
    text = path.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert ":/" not in text and ":\\" not in text


def test_command_accepts_positional_prompt_out_and_attempt_override(
        tmp_path, monkeypatch, capsys):
    calls = {}
    _fake_generate(monkeypatch, calls)
    args = _args(tmp_path, max_attempts=5)
    code = run_generate_command(args, _cfg(), Path(
        "packs"), lambda settings: object())
    assert code == 0
    assert calls["requirement"] == "Build a plate"
    assert calls["out_dir"] == args.out
    assert calls["settings"]["max_attempts"] == 5
    assert calls["part_id"] == PART_ID and calls["pack"] == "stub"
    assert (args.out / "result.toml").is_file()
    assert "Status: ok" in capsys.readouterr().out


def test_command_accepts_a_prompt_file(tmp_path, monkeypatch):
    calls = {}
    _fake_generate(monkeypatch, calls)
    prompt = tmp_path / "requirement.txt"
    prompt.write_text("Build from a file\n", encoding="utf-8")
    args = _args(tmp_path, prompt=None, prompt_file=prompt)
    code = run_generate_command(args, _cfg(), Path(
        "packs"), lambda settings: object())
    assert code == 0
    assert calls["requirement"] == "Build from a file\n"


@pytest.mark.parametrize("prompt,prompt_file", [
    (None, None), ("Build a plate", Path("requirement.txt")),
])
def test_command_refuses_missing_or_competing_prompts(
        tmp_path, prompt, prompt_file, capsys):
    args = _args(tmp_path, prompt=prompt, prompt_file=prompt_file)
    code = run_generate_command(args, _cfg(), Path(
        "packs"), lambda settings: object())
    assert code == 2
    assert "exactly one" in capsys.readouterr().out


def test_command_turns_missing_api_key_into_exit_two(tmp_path, capsys):
    def denied(settings):
        raise AgentError("the API key is missing")

    code = run_generate_command(
        _args(tmp_path), _cfg(), Path("packs"), denied)
    output = capsys.readouterr().out
    assert code == 2 and "API key" in output
    assert "Traceback" not in output


def test_command_returns_one_for_an_unsuccessful_generation(
        tmp_path, monkeypatch, capsys):
    _fake_generate(monkeypatch, {}, ok=False)
    args = _args(tmp_path)
    code = run_generate_command(args, _cfg(), Path(
        "packs"), lambda settings: object())
    assert code == 1
    assert (args.out / "result.toml").is_file()
    assert "Status: error" in capsys.readouterr().out
