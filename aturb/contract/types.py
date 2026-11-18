"""Types exchanged across the runner contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from aturb.contract import CONTRACT_VERSION


class FailureKind(str, Enum):
    """The fixed list of ways a build can fail."""

    REJECTED_UNSAFE = "rejected_unsafe"  # static safety check refused the part file
    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    # built, but the CAD reported failed features
    INVALID_GEOMETRY = "invalid_geometry"
    EXPORT_FAILED = "export_failed"
    RUNNER_CRASH = "runner_crash"  # runner produced no result at all
    INPUT_ERROR = "input_error"  # bad request: part not found, ambiguous, wrong language


@dataclass(frozen=True)
class BuildRequest:
    """The data the core sends to a runner."""

    project_root: str  # absolute path; internal to core and runner only, never shown in events
    part_id: str  # e.g. "plt0001"; the pack resolves this to a file
    language: str  # language tag; must match the pack's info().language
    outputs: tuple[str, ...] = ("native", "step")
    timeout_s: int = 60  # starting default

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this request."""
        return {
            "project_root": self.project_root,
            "part_id": self.part_id,
            "language": self.language,
            "outputs": list(self.outputs),
            "timeout_s": self.timeout_s,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BuildRequest":
        """Rebuild a request from a dict, restoring outputs as a tuple."""
        return cls(
            project_root=d["project_root"],
            part_id=d["part_id"],
            language=d["language"],
            outputs=tuple(d["outputs"]),
            timeout_s=d["timeout_s"],
        )


@dataclass(frozen=True)
class BuildResult:
    """The data a runner returns to the core."""

    status: str  # "ok" or "failed"
    failure_kind: FailureKind | None = None
    error_text: str = ""
    log_path: str = ""  # relative to project_root, forward slashes
    artifacts: dict[str, str] = field(
        default_factory=dict)  # keys "native", "step"
    native_diagnostics: dict = field(
        default_factory=dict)  # informational only
    duration_ms: int = 0
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Check that status and failure_kind agree."""
        if self.status not in ("ok", "failed"):
            raise ValueError(
                f"status must be 'ok' or 'failed', got {self.status!r}")
        if self.status == "failed" and self.failure_kind is None:
            raise ValueError("a failed result must carry a failure_kind")
        if self.status == "ok" and self.failure_kind is not None:
            raise ValueError("an ok result must not carry a failure_kind")

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this result."""
        return {
            "status": self.status,
            "failure_kind": self.failure_kind.value if self.failure_kind is not None else None,
            "error_text": self.error_text,
            "log_path": self.log_path,
            "artifacts": dict(self.artifacts),
            "native_diagnostics": dict(self.native_diagnostics),
            "duration_ms": self.duration_ms,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BuildResult":
        """Rebuild a result from a dict, restoring failure_kind as an enum member."""
        failure_kind = d["failure_kind"]
        return cls(
            status=d["status"],
            failure_kind=FailureKind(
                failure_kind) if failure_kind is not None else None,
            error_text=d["error_text"],
            log_path=d["log_path"],
            artifacts=dict(d["artifacts"]),
            native_diagnostics=dict(d["native_diagnostics"]),
            duration_ms=d["duration_ms"],
            contract_version=d["contract_version"],
        )


@dataclass(frozen=True)
class PackInfo:
    """How a runner describes itself."""

    name: str
    language: str
    version: str

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict of this pack info."""
        return {
            "name": self.name,
            "language": self.language,
            "version": self.version,
        }
