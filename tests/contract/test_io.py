"""Tests for the atomic JSON helpers of the runner contract."""

from __future__ import annotations

from aturb.contract.io import read_json, write_json


def test_write_then_read_returns_same_dict(tmp_path):
    """A written dict reads back unchanged."""
    target = tmp_path / "request.json"
    data = {"part_id": "plt0001", "outputs": ["native", "step"]}

    write_json(target, data)

    assert read_json(target) == data


def test_write_replaces_existing_file(tmp_path):
    """Writing over an existing file replaces its contents."""
    target = tmp_path / "result.json"
    target.write_text('{"status": "old"}', encoding="utf-8")

    write_json(target, {"status": "new"})

    assert read_json(target) == {"status": "new"}


def test_write_leaves_no_temporary_file(tmp_path):
    """Writing leaves only the destination file in the folder."""
    target = tmp_path / "result.json"

    write_json(target, {"status": "ok"})

    assert [p.name for p in tmp_path.iterdir()] == ["result.json"]
