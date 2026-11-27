"""Atomic single-file persistence for the workspace of the core.

A reader must never see a half-written file, so every writer writes into a
temporary file in the same folder, flushes it, flushes it to the disk and
then moves it onto the destination with ``os.replace``.

``os.replace`` guarantees that the replacement of ONE file is atomic: a reader
sees either the old file or the new one, never a mixture. It does NOT make a
group of files atomic: two files written one after the other can still be seen
half-updated, so a transaction over several files needs its own journal.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write a text to a file atomically and return the path of the file.

    The parent folder is made when it is not there. The text is written into a
    temporary file in the same folder, flushed, flushed to the disk and then
    moved onto the destination with ``os.replace``, so a reader never sees a
    half-written file. The temporary file is removed when anything fails, and
    the destination keeps the content it had.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return path


def atomic_copy(src: Path, dst: Path) -> Path:
    """Copy a file into place atomically and return the path of the copy.

    The bytes are copied into a temporary file in the folder of the
    destination, flushed, flushed to the disk and then moved onto the
    destination with ``os.replace``. The replacement of the one file is
    atomic; a copy of several files is not a transaction.
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        dir=str(dst.parent), prefix=dst.name + ".", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(src.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, dst)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return dst
