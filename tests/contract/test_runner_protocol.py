"""Tests for the runner protocol."""

from __future__ import annotations

from aturb.contract.runner import Runner


def test_runner_has_two_methods():
    """The Runner protocol exposes exactly info() and build()."""
    public = {
        name
        for name, value in vars(Runner).items()
        if not name.startswith("_") and callable(value)
    }

    assert public == {"info", "build"}
