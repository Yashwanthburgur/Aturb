"""Unit tests for the failed-feature rule recorded in docs/api_notes/freecad.md."""

from __future__ import annotations

from packs.freecad.harness.fc_state import failed_feature_names


class FakeObject:
    """A stand-in for a FreeCAD document object."""

    def __init__(self, name: str, state: list[str]):
        self.Name = name
        self.State = state


def test_invalid_feature_is_reported():
    """A feature whose State carries Invalid is a failed feature."""
    objects = [FakeObject("Pad", ["Touched", "Invalid"])]

    assert failed_feature_names(objects) == ["Pad"]


def test_touched_container_is_not_a_failure():
    """A container that is only Touched is not a failed feature."""
    objects = [
        FakeObject("Body", ["Touched"]),
        FakeObject("EmptySketch", ["Up-to-date"]),
        FakeObject("Pad", ["Touched", "Invalid"]),
    ]

    assert failed_feature_names(objects) == ["Pad"]


def test_working_features_are_not_reported():
    """Up-to-date features are never reported as failures."""
    objects = [FakeObject("Box", ["Up-to-date"])]

    assert failed_feature_names(objects) == []
