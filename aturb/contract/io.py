"""Atomic JSON file helpers for the runner contract.

A request file and a result file are written by one process and read by
another, so a reader must never see a half-written file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    """Write data as JSON to path, replacing the destination atomically.

    The JSON is written to a temporary file in the same folder and then moved
    onto the destination with os.replace, so a reader never sees a partly
    written file. The temporary file is removed if anything fails.
    """
    path = Path(path)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def read_json(path: Path) -> dict:
    """Read UTF-8 JSON from path and return it as a dict."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
