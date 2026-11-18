"""FreeCAD runner: launches the CAD in a child process and reports the result."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from aturb.contract.io import read_json, write_json
from aturb.contract.types import BuildRequest, BuildResult, FailureKind, PackInfo
from aturb.workspace.paths import PathEscapeError, resolve_inside, to_rel
from packs.freecad.precheck import precheck

ALLOWED_ENV = {
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT",
    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH",
    "COMPUTERNAME", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS",
}


def child_env(base: Mapping[str, str], job_path: Path) -> dict[str, str]:
    """Return only the allowed environment keys plus ATURB_REQUEST."""
    env = {
        key: value for key, value in base.items()
        if key.upper() in ALLOWED_ENV
    }
    env["ATURB_REQUEST"] = str(job_path)
    return env


def find_part_file(project_root: Path, part_id: str) -> Path | str:
    """Return the single part file for part_id, or an error string."""
    parts_dir = resolve_inside(project_root, "parts")
    matches = sorted(parts_dir.glob(f"{part_id}_*.py"))
    exact = sorted(parts_dir.glob(f"{part_id}.py"))
    matches = matches + exact
    if not matches:
        return f"no part file for {part_id}"
    if len(matches) > 1:
        names = ", ".join(p.name for p in matches)
        return f"ambiguous part id {part_id}: {names}"
    return matches[0]


def convert_artifacts(project_root: Path, artifacts: dict) -> dict | str:
    """Make artifact paths project-relative; return an error string if outside."""
    converted: dict[str, str] = {}
    for key, value in artifacts.items():
        try:
            converted[key] = to_rel(project_root, Path(value))
        except PathEscapeError:
            return f"artifact {key!r} points outside the project"
    return converted


def clear_out_dir(out_dir: Path) -> None:
    """Delete everything inside out_dir, without following links out of it."""
    root = out_dir.resolve()
    for child in out_dir.iterdir():
        if not child.resolve().is_relative_to(root):
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def parse_result(raw, project_root: Path) -> dict | str:
    """Turn the harness result into BuildResult fields, or an error string."""
    if not isinstance(raw, dict):
        return "malformed result: expected a JSON object"
    status = raw.get("status")
    if status not in ("ok", "failed"):
        return f"malformed result: unknown status {status!r}"
    kind_value = raw.get("failure_kind")
    if status == "ok" and kind_value is not None:
        return "malformed result: an ok result carries a failure_kind"
    if status == "failed" and kind_value is None:
        return "malformed result: a failed result carries no failure_kind"
    kind = None
    if kind_value is not None:
        try:
            kind = FailureKind(kind_value)
        except ValueError:
            return f"malformed result: unknown failure_kind {kind_value!r}"
    error_text = raw.get("error_text", "")
    if not isinstance(error_text, str):
        return "malformed result: error_text is not a string"
    diagnostics = raw.get("native_diagnostics", {})
    if not isinstance(diagnostics, dict):
        return "malformed result: native_diagnostics is not an object"
    artifacts = raw.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return "malformed result: artifacts is not an object"
    converted = convert_artifacts(project_root, artifacts)
    if isinstance(converted, str):
        return converted
    return {
        "status": status,
        "failure_kind": kind,
        "error_text": error_text,
        "artifacts": converted,
        "native_diagnostics": diagnostics,
    }


class FreeCADRunner:
    """Builds one part by running the harness inside the CAD process."""

    def __init__(self, settings: dict, pack_dir: Path):
        self.settings = settings
        self.pack_dir = pack_dir

    def info(self) -> PackInfo:
        """Describe the FreeCAD pack."""
        return PackInfo(name="freecad", language="python-freecad", version="0.1")

    def harness_path(self) -> Path:
        """Return the script the child process runs inside the CAD."""
        return self.pack_dir / "harness" / "build_part.py"

    def build(self, request: BuildRequest) -> BuildResult:
        """Build one part and report what happened."""
        start = time.perf_counter()

        def done(status, failure_kind=None, error_text="", artifacts=None,
                 log_path="", native_diagnostics=None):
            return BuildResult(
                status=status,
                failure_kind=failure_kind,
                error_text=error_text,
                log_path=log_path,
                artifacts=artifacts or {},
                native_diagnostics=native_diagnostics or {},
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        if request.language != "python-freecad":
            return done(
                "failed", FailureKind.INPUT_ERROR,
                f"language mismatch: request {request.language!r} "
                f"!= pack language 'python-freecad'")

        project_root = Path(request.project_root)
        part = find_part_file(project_root, request.part_id)
        if isinstance(part, str):
            return done("failed", FailureKind.INPUT_ERROR, part)

        try:
            source = part.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return done(
                "failed", FailureKind.INPUT_ERROR,
                f"part file {part.name} is not valid UTF-8 text")
        verdict, reasons = precheck(source)
        if verdict == "syntax_error":
            return done("failed", FailureKind.SYNTAX_ERROR, reasons[0])
        if verdict == "rejected_unsafe":
            return done(
                "failed", FailureKind.REJECTED_UNSAFE, "\n".join(reasons))

        out_dir = resolve_inside(project_root, f"out/{request.part_id}")
        if out_dir.exists():
            clear_out_dir(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        job = {
            "job_version": 1,
            "part_id": request.part_id,
            "part_file": str(part),
            "project_root": str(project_root),
            "out_dir": str(out_dir),
            "outputs": list(request.outputs),
            "result_path": str(out_dir / "result.json"),
        }
        job_path = out_dir / "job.json"
        write_json(job_path, job)
        log_path = out_dir / "build.log"

        cmd = self.settings.get("cmd", "")
        if not cmd:
            return done(
                "failed", FailureKind.RUNNER_CRASH,
                "packs.freecad.cmd is not configured",
                log_path=to_rel(project_root, log_path))

        with log_path.open("w", encoding="utf-8") as log:
            try:
                proc = subprocess.Popen(
                    [cmd, str(self.harness_path())],
                    cwd=str(project_root),
                    env=child_env(os.environ, job_path),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            except OSError as exc:
                return done(
                    "failed", FailureKind.RUNNER_CRASH,
                    f"cannot start the CAD process: {exc}",
                    log_path=to_rel(project_root, log_path))
            try:
                proc.wait(timeout=request.timeout_s)
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True)
                try:
                    proc.kill()
                except OSError:
                    pass
                proc.wait()
                return done(
                    "failed", FailureKind.TIMEOUT,
                    f"build exceeded {request.timeout_s} s",
                    log_path=to_rel(project_root, log_path))

        result_path = out_dir / "result.json"
        if not result_path.is_file():
            tail = ""
            if log_path.is_file():
                lines = log_path.read_text(encoding="utf-8").splitlines()
                tail = "\n".join(lines[-20:])  # 20 is a starting default
            return done(
                "failed", FailureKind.RUNNER_CRASH,
                "no result file; last log lines:\n" + tail,
                log_path=to_rel(project_root, log_path))

        try:
            raw = read_json(result_path)
        except (OSError, ValueError) as exc:
            return done(
                "failed", FailureKind.RUNNER_CRASH,
                f"cannot read the result file: {exc}",
                log_path=to_rel(project_root, log_path))

        parsed = parse_result(raw, project_root)
        if isinstance(parsed, str):
            return done(
                "failed", FailureKind.RUNNER_CRASH, parsed,
                log_path=to_rel(project_root, log_path))

        return done(
            parsed["status"],
            parsed["failure_kind"],
            parsed["error_text"],
            artifacts=parsed["artifacts"],
            log_path=to_rel(project_root, log_path),
            native_diagnostics=parsed["native_diagnostics"],
        )
