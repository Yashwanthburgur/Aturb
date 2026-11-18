"""Stub runner: builds by copying the packaged fixture STEP, no CAD involved."""

from __future__ import annotations

import time
from importlib.resources import files
from pathlib import Path

from aturb.contract.types import BuildRequest, BuildResult, FailureKind, PackInfo
from aturb.workspace.paths import resolve_inside, to_rel

FIXTURE_RESOURCE = "fixtures/plate_2holes.step"


def fixture_bytes() -> bytes:
    """Return the STEP fixture shipped inside this package."""
    resource = files(__package__).joinpath(FIXTURE_RESOURCE)
    return resource.read_bytes()


class StubRunner:
    """A runner that is not a CAD at all; proves the core never needs one."""

    def __init__(self, settings: dict, pack_dir: Path):
        self.settings = settings
        self.pack_dir = pack_dir

    def info(self) -> PackInfo:
        """Describe the stub pack."""
        return PackInfo(name="stub", language="stub-text", version="0.1")

    def build(self, request: BuildRequest) -> BuildResult:
        """Build one part by copying the fixture STEP, or fail scripted."""
        start = time.perf_counter()

        def failed(kind: FailureKind, message: str) -> BuildResult:
            return BuildResult(
                status="failed",
                failure_kind=kind,
                error_text=message,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        if request.language != "stub-text":
            return failed(
                FailureKind.INPUT_ERROR,
                f"language mismatch: request {request.language!r} "
                f"!= pack language 'stub-text'",
            )

        project_root = Path(request.project_root)
        parts_dir = resolve_inside(project_root, "parts")
        matches = sorted(parts_dir.glob(f"{request.part_id}_*.stub"))
        matches += sorted(parts_dir.glob(f"{request.part_id}.stub"))
        if not matches:
            return failed(
                FailureKind.INPUT_ERROR, f"no part file for {request.part_id}")
        if len(matches) > 1:
            names = ", ".join(p.name for p in matches)
            return failed(
                FailureKind.INPUT_ERROR,
                f"ambiguous part id {request.part_id}: {names}",
            )

        part_file = matches[0]
        try:
            text = part_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return failed(
                FailureKind.INPUT_ERROR,
                f"part file {part_file.name} is not valid UTF-8 text",
            )
        lines = text.splitlines()
        if not lines:
            return failed(
                FailureKind.INPUT_ERROR,
                f"part file {part_file.name} is empty",
            )

        first_line = lines[0]
        if first_line.startswith("# STUB: fail="):
            kind = first_line.removeprefix("# STUB: fail=").strip()
            return failed(
                FailureKind(kind), f"scripted failure: {kind}")

        try:
            payload = fixture_bytes()
        except OSError as exc:
            return failed(
                FailureKind.RUNNER_CRASH,
                f"the stub fixture {FIXTURE_RESOURCE} is missing: {exc}",
            )

        out_dir = resolve_inside(project_root, f"out/{request.part_id}")
        out_dir.mkdir(parents=True, exist_ok=True)
        step_path = out_dir / f"{request.part_id}.step"
        native_path = out_dir / f"{request.part_id}.stubnative"
        log_path = out_dir / "build.log"
        step_path.write_bytes(payload)
        native_path.write_text("stub native file", encoding="utf-8")
        log_path.write_text("stub build ok", encoding="utf-8")

        return BuildResult(
            status="ok",
            log_path=to_rel(project_root, log_path),
            artifacts={
                "native": to_rel(project_root, native_path),
                "step": to_rel(project_root, step_path),
            },
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
