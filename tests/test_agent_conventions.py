"""Tests for the convention checker of the agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from aturb.agent.conventions import check_conventions

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_PART = REPO_ROOT / "projects" / "demo" / "parts" / "plt0001_base_plate.py"

COMPLIANT = '''"""PLT0001 Base plate.

Units: millimetres.
"""

# --- PARAMS ---
LENGTH_MM = 120.0
THICKNESS_MM = 5.0
# --- END PARAMS ---


def build(doc):
    return doc
'''


def test_a_compliant_file_has_no_findings():
    """A part file that follows every rule produces no finding."""
    assert check_conventions("plt0001", ".py", COMPLIANT) == []


def test_the_demo_part_has_no_findings():
    """The committed demo part follows every rule."""
    text = DEMO_PART.read_text(encoding="utf-8")

    assert check_conventions("plt0001", ".py", text) == []


def test_an_empty_part_id_is_reported():
    """A part without an identity breaks C1."""
    findings = check_conventions("", ".py", COMPLIANT)

    assert [finding.split(":")[0] for finding in findings] == ["C1"]
    assert "part ID" in findings[0]


def test_a_part_id_with_an_underscore_is_reported():
    """A part ID that is not the first segment of the file name breaks C1."""
    findings = check_conventions("plt_001", ".py", COMPLIANT)

    assert [finding.split(":")[0] for finding in findings] == ["C1"]
    assert "underscore" in findings[0]


def test_an_extension_without_a_dot_is_reported():
    """An extension that is not an extension breaks C1."""
    findings = check_conventions("plt0001", "py", COMPLIANT)

    assert [finding.split(":")[0] for finding in findings] == ["C1"]
    assert "dot" in findings[0]


def test_a_missing_parameter_block_is_reported():
    """A file without the marked parameter block breaks C2."""
    text = COMPLIANT.replace("# --- PARAMS ---\n", "").replace("# --- END PARAMS ---\n", "")

    findings = check_conventions("plt0001", ".py", text)

    assert [finding.split(":")[0] for finding in findings] == ["C2"]
    assert "PARAMS" in findings[0]


def test_an_invalid_constant_name_is_reported():
    """A parameter constant that does not end with _MM breaks C2."""
    text = COMPLIANT.replace("LENGTH_MM = 120.0", "LENGTH = 120.0")

    findings = check_conventions("plt0001", ".py", text)

    assert [finding.split(":")[0] for finding in findings] == ["C2"]
    assert "line 7" in findings[0]
    assert "LENGTH" in findings[0]


def test_a_parameter_block_below_the_code_is_reported():
    """A parameter block that is not at the top of the file breaks C2."""
    text = COMPLIANT.replace("# --- PARAMS ---", "import os\n\n# --- PARAMS ---")

    findings = check_conventions("plt0001", ".py", text)

    assert [finding.split(":")[0] for finding in findings] == ["C2"]
    assert "top of the file" in findings[0]


def test_a_missing_millimetre_declaration_is_reported():
    """A file that does not state its units breaks C3."""
    text = COMPLIANT.replace("Units: millimetres.\n", "")

    findings = check_conventions("plt0001", ".py", text)

    assert [finding.split(":")[0] for finding in findings] == ["C3"]
    assert "millimetres" in findings[0]


@pytest.mark.parametrize("line,label", [
    ('PATH = "/home/user/parts"', "absolute path"),
    ('PATH = "C:/Users/user/parts"', "drive-letter path"),
])
def test_a_machine_value_is_reported(line, label):
    """An absolute path or a drive-letter path breaks C5."""
    text = COMPLIANT.replace("# --- END PARAMS ---", f"# --- END PARAMS ---\n{line}")

    findings = check_conventions("plt0001", ".py", text)

    assert [finding.split(":")[0] for finding in findings] == ["C5"]
    assert label in findings[0]


def test_every_finding_names_its_convention():
    """Every finding names the convention it breaks and says what is wrong."""
    findings = check_conventions("", "py", COMPLIANT)

    assert findings
    for finding in findings:
        assert finding.startswith(("C1:", "C2:", "C3:", "C5:"))
        assert len(finding) > len("C1:")


@pytest.mark.parametrize("text", [
    "",
    "not code at all",
    "'''",
    "x = 1",
    "raise SystemExit('the part file was executed')",
])
def test_the_checker_never_raises(text):
    """A part file the checker cannot read is reported, never raised."""
    findings = check_conventions("plt0001", ".py", text)

    assert isinstance(findings, list)
