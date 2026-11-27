"""Build every part of an assembly and verify the assembly as a whole.

The build follows the runner contract: every unique part of the assembly is
built on its own, exactly as a single part is built, and the exported STEP of
each part is then composed and verified as one assembly.

The outcome is written to `out/assemblies/<assembly_id>/` inside the project:
the compound STEP file and a portable `assembly_result.toml` that holds the
verdict. The result file holds no host path.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aturb.agent.record import toml_string
from aturb.assembly.manifest import AssemblyError, AssemblySpec, load_assembly
from aturb.contract.runner import Runner
from aturb.contract.types import BuildRequest, BuildResult
from aturb.verify.assembly import (
    AssemblyReport,
    PairVerification,
    compose_assembly_step,
    verify_assembly,
)
from aturb.workspace.paths import PathEscapeError, resolve_inside, to_rel

OUT_DIR = "out"
ASSEMBLY_DIR = "assemblies"
RESULT_FILE_NAME = "assembly_result.toml"


@dataclass(frozen=True)
class AssemblyBuildResult:
    """The outcome of one assembly build.

    The two paths are relative to the project root and use forward slashes, so
    they hold no host path. The `assembly_step` is the compound STEP file and
    the `manifest_path` is the result file of the assembly.
    """

    status: str
    assembly_id: str
    assembly_name: str
    part_results: dict[str, BuildResult]
    assembly_step: str
    manifest_path: str
    report: AssemblyReport | None
    error: str


def build_assembly(
    project_root: Path,
    assembly_path: Path,
    runner: Runner,
    *,
    timeout_s: int = 60,  # starting default
) -> AssemblyBuildResult:
    """Build every part of the assembly and verify the assembly as a whole.

    Raises ``AssemblyError`` when the assembly file lies outside the project or
    when its manifest cannot be read. A part that fails to build, a part that
    produces no STEP file, a clash between two components and a mate whose
    clearance is not met all give a failed result and a clear error.
    """
    project_root = Path(project_root).resolve()
    manifest_path = _resolve_manifest(project_root, assembly_path)
    spec = load_assembly(manifest_path)
    assembly_file = to_rel(project_root, manifest_path)
    part_results = _build_parts(spec, project_root, runner, timeout_s)
    failure = _part_failure(part_results)
    if failure:
        return _failed_build(spec, part_results, failure, project_root,
                             assembly_file)
    out_dir = _output_dir(project_root, spec.assembly_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    step_path = out_dir / f"{spec.assembly_id}.step"
    try:
        part_steps = _part_steps(part_results, project_root)
        compose_assembly_step(spec, part_steps, step_path)
        report = verify_assembly(spec, part_steps)
    except (AssemblyError, PathEscapeError) as exc:
        return _failed_build(spec, part_results, str(exc), project_root,
                             assembly_file)
    error = _verdict_error(report)
    status = "failed" if error else "ok"
    _write_result(out_dir, spec, report, status, error, step_path.name,
                  assembly_file)
    return AssemblyBuildResult(
        status=status,
        assembly_id=spec.assembly_id,
        assembly_name=spec.name,
        part_results=part_results,
        assembly_step=to_rel(project_root, step_path),
        manifest_path=to_rel(project_root, out_dir / RESULT_FILE_NAME),
        report=report,
        error=error,
    )


def _resolve_manifest(project_root: Path, assembly_path: Path) -> Path:
    """Return the manifest of the assembly, refused when it leaves the project."""
    try:
        return resolve_inside(project_root, assembly_path)
    except PathEscapeError as exc:
        raise AssemblyError(
            f"the assembly file lies outside the project: {exc}") from exc


def _build_parts(spec: AssemblySpec, project_root: Path, runner: Runner,
                 timeout_s: int) -> dict[str, BuildResult]:
    """Build every unique part of the assembly through the runner contract."""
    results: dict[str, BuildResult] = {}
    for part_id in _unique_part_ids(spec):
        results[part_id] = runner.build(BuildRequest(
            project_root=str(project_root),
            part_id=part_id,
            language=runner.info().language,
            timeout_s=timeout_s,
        ))
    return results


def _unique_part_ids(spec: AssemblySpec) -> tuple[str, ...]:
    """Return the part ids of the assembly, each of them once, in order."""
    seen: list[str] = []
    for component in spec.components:
        if component.part_id not in seen:
            seen.append(component.part_id)
    return tuple(seen)


def _part_failure(part_results: dict[str, BuildResult]) -> str:
    """Say why a part of the assembly cannot be used, or nothing when it can."""
    for part_id, result in part_results.items():
        if result.status != "ok":
            kind = result.failure_kind.value if result.failure_kind else "unknown"
            detail = _first_line(result.error_text)
            return f"the part {part_id} failed to build ({kind}): {detail}"
        if not result.artifacts.get("step"):
            return f"the part {part_id} produced no STEP file"
    return ""


def _part_steps(part_results: dict[str, BuildResult],
                project_root: Path) -> dict[str, Path]:
    """Return the STEP file of every part, resolved inside the project."""
    return {
        part_id: resolve_inside(project_root, result.artifacts["step"])
        for part_id, result in part_results.items()
    }


def _output_dir(project_root: Path, assembly_id: str) -> Path:
    """Return the output folder of the assembly inside the project."""
    return resolve_inside(project_root, f"{OUT_DIR}/{ASSEMBLY_DIR}/{assembly_id}")


def _verdict_error(report: AssemblyReport) -> str:
    """Say why the assembly is not acceptable, or nothing when it is."""
    if not report.all_valid:
        return "the assembly holds geometry that is not valid"
    clashing = [pair for pair in report.pairs if pair.intersects]
    if clashing:
        names = ", ".join(
            f"{pair.part_a} <-> {pair.part_b}" for pair in clashing)
        return f"the components interfere: {names}"
    unmet = [pair for pair in report.pairs if not pair.mate_ok]
    if unmet:
        names = ", ".join(f"{pair.part_a} <-> {pair.part_b}" for pair in unmet)
        return f"the mate clearance is not met: {names}"
    return ""


def _failed_build(spec: AssemblySpec, part_results: dict[str, BuildResult],
                  error: str, project_root: Path,
                  assembly_file: str) -> AssemblyBuildResult:
    """Write the failed result of the assembly and return it.

    The compound STEP of an earlier run is removed, so a failed build never
    leaves a stale assembly behind that the result file does not describe.
    """
    out_dir = _output_dir(project_root, spec.assembly_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{spec.assembly_id}.step").unlink(missing_ok=True)
    _write_result(out_dir, spec, None, "failed", error, "", assembly_file)
    return AssemblyBuildResult(
        status="failed",
        assembly_id=spec.assembly_id,
        assembly_name=spec.name,
        part_results=part_results,
        assembly_step="",
        manifest_path=to_rel(project_root, out_dir / RESULT_FILE_NAME),
        report=None,
        error=error,
    )


def _write_result(out_dir: Path, spec: AssemblySpec, report: AssemblyReport | None,
                  status: str, error: str, step_file: str,
                  assembly_file: str) -> Path:
    """Write the portable result file of the assembly and return its path."""
    path = out_dir / RESULT_FILE_NAME
    _atomic_write(path, _result_text(
        spec, report, status, error, step_file, assembly_file))
    return path


def _result_text(spec: AssemblySpec, report: AssemblyReport | None, status: str,
                 error: str, step_file: str, assembly_file: str) -> str:
    """Return the text of the portable result file of the assembly."""
    if report is None:
        component_count = len(spec.components)
        all_valid = has_interference = all_mates_ok = False
        total_volume = 0.0
        bbox_min = bbox_max = bbox_size = (0.0, 0.0, 0.0)
        pairs: tuple[PairVerification, ...] = ()
    else:
        component_count = report.component_count
        all_valid = report.all_valid
        has_interference = report.has_interference
        all_mates_ok = report.all_mates_ok
        total_volume = report.total_volume
        bbox_min = report.bbox_min
        bbox_max = report.bbox_max
        bbox_size = report.bbox_size
        pairs = report.pairs
    lines = [
        f"status = {toml_string(status)}",
        f"assembly_id = {toml_string(spec.assembly_id)}",
        f"assembly_name = {toml_string(spec.name)}",
        f"assembly_file = {toml_string(assembly_file)}",
        f"step_file = {toml_string(step_file)}",
        f"component_count = {int(component_count)}",
        f"all_valid = {_bool(all_valid)}",
        f"has_interference = {_bool(has_interference)}",
        f"all_mates_ok = {_bool(all_mates_ok)}",
        f"total_volume = {repr(float(total_volume))}",
        f"bbox_min = {_floats(bbox_min)}",
        f"bbox_max = {_floats(bbox_max)}",
        f"bbox_size = {_floats(bbox_size)}",
        f"error = {toml_string(error)}",
    ]
    for pair in pairs:
        lines.append("")
        lines.append("[[pairs]]")
        lines.append(f"part_a = {toml_string(pair.part_a)}")
        lines.append(f"part_b = {toml_string(pair.part_b)}")
        lines.append(f"intersects = {_bool(pair.intersects)}")
        lines.append(
            f"overlap_volume_mm3 = {repr(float(pair.overlap_volume_mm3))}")
        lines.append(
            f"min_clearance_mm = {repr(float(pair.min_clearance_mm))}")
        lines.append(f"mate_ok = {_bool(pair.mate_ok)}")
        lines.append(f"note = {toml_string(pair.note)}")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    """Write a text to a file through a temporary file in the same folder."""
    handle, name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _bool(value: bool) -> str:
    """Return a TOML boolean."""
    return "true" if value else "false"


def _floats(values: tuple[float, float, float]) -> str:
    """Return a TOML array of three numbers."""
    return "[" + ", ".join(repr(float(value)) for value in values) + "]"


def _first_line(text: str) -> str:
    """Return the first line of a text, or the text when it has one line."""
    lines = text.splitlines()
    return lines[0] if lines else ""
