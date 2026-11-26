"""Tests for the parameter block of a part file.

The extractor reads the marked block of a part file as text. It never parses
the file as code and never executes it, so a part file in any language is read
the same way.
"""

from __future__ import annotations

from aturb.agent.params import ParamEntry, extract_params, format_params_block

SOURCE = '''"""A plate. Units: millimetres."""
# --- PARAMS ---
LENGTH_MM = 120.0  # the length of the plate
WIDTH_MM = 60.0
THICKNESS_MM = 5.0
# --- END PARAMS ---
'''


def test_the_block_is_read_as_entries():
    """Every top-level assignment of the block is one entry."""
    params = extract_params(SOURCE)

    assert params == (
        ParamEntry("LENGTH_MM", "120.0", "the length of the plate"),
        ParamEntry("WIDTH_MM", "60.0"),
        ParamEntry("THICKNESS_MM", "5.0"),
    )


def test_a_source_without_markers_has_no_parameter():
    """A file without the markers holds no parameter."""
    assert extract_params("LENGTH_MM = 120.0\n") == ()


def test_an_empty_block_has_no_parameter():
    """A block with no assignment holds no parameter."""
    source = "# --- PARAMS ---\n# --- END PARAMS ---\n"

    assert extract_params(source) == ()


def test_the_markers_in_the_wrong_order_hold_no_parameter():
    """A block that ends before it starts holds no parameter."""
    source = "# --- END PARAMS ---\nLENGTH_MM = 120.0\n# --- PARAMS ---\n"

    assert extract_params(source) == ()


def test_blank_and_comment_lines_are_left_out():
    """A blank line and a comment-only line hold no parameter."""
    source = ("# --- PARAMS ---\n\n# a note\nLENGTH_MM = 120.0\n"
              "# --- END PARAMS ---\n")

    assert extract_params(source) == (ParamEntry("LENGTH_MM", "120.0"),)


def test_an_indented_assignment_is_not_a_top_level_parameter():
    """An indented line is not a top-level assignment."""
    source = "# --- PARAMS ---\n    LENGTH_MM = 120.0\n# --- END PARAMS ---\n"

    assert extract_params(source) == ()


def test_a_marker_inside_a_value_is_part_of_the_value():
    """A marker inside a quoted value is not the start of a comment."""
    source = '# --- PARAMS ---\nLABEL = "a # b"\n# --- END PARAMS ---\n'

    assert extract_params(source) == (ParamEntry("LABEL", '"a # b"'),)


def test_an_assignment_without_a_value_is_left_out():
    """A name with no value holds no parameter."""
    source = "# --- PARAMS ---\nLENGTH_MM =\n# --- END PARAMS ---\n"

    assert extract_params(source) == ()


def test_the_block_is_formatted_for_the_prompt():
    """The block names the parameters and their comments."""
    block = format_params_block(extract_params(SOURCE))

    assert block == (
        "Current parameters:\n"
        "- LENGTH_MM = 120.0 (the length of the plate)\n"
        "- WIDTH_MM = 60.0\n"
        "- THICKNESS_MM = 5.0")


def test_no_parameter_is_an_empty_block():
    """An empty list of parameters is an empty text."""
    assert format_params_block(()) == ""
    assert format_params_block([]) == ""
