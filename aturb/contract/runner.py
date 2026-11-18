"""The protocol every backend pack implements."""

from __future__ import annotations

from typing import Protocol

from aturb.contract.types import BuildRequest, BuildResult, PackInfo


class Runner(Protocol):
    """A runner builds one part from its file and reports what happened. It never exposes CAD operations."""  # noqa: E501

    # Every runner class is constructed as RunnerClass(settings: dict, pack_dir: Path).
    def info(self) -> PackInfo:
        """Describe the pack: its name, its language and its version."""
        ...

    def build(self, request: BuildRequest) -> BuildResult:
        """Build one part and report what happened."""
        ...
