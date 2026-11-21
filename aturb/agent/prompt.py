"""Compose the prompt of one agent run and name it.

The prompt is built in a fixed order from five sections: the core instruction,
the prompt of the pack, the requirement of the task, the expected values of
the part and the output contract. The order never changes, so the same inputs
always give the same prompt.

The version of a prompt is the first sixteen hexadecimal characters of the
SHA-256 of the exact text that is sent to the model. A hash needs no registry
and cannot drift from the text.
"""

from __future__ import annotations

import hashlib

CORE_INSTRUCTION = """\
Write one part file and nothing else. Return the complete source of a single
part file. Do not explain it, do not describe it, and do not put anything
around it.
"""

OUTPUT_CONTRACT = """\
Output contract: reply with the content of the file and nothing else. No
explanation, no summary and no text around it.
"""

FENCE = "```"

VERSION_LENGTH = 16


def compose_prompt(pack_prompt: str, requirement: str, expectations: str) -> str:
    """Return the prompt of one agent run.

    The five sections are joined in a fixed order with one blank line between
    them: the core instruction, the pack prompt, the requirement, the
    expectations and the output contract. Every section is trimmed, so the
    blank line between two sections is always exactly one.

    An empty pack prompt or an empty requirement is refused: the prompt would
    be missing the instructions of the pack or the intent of the task.
    """
    if not pack_prompt.strip():
        raise ValueError("the pack prompt is empty")
    if not requirement.strip():
        raise ValueError("the requirement is empty")
    sections = (
        CORE_INSTRUCTION,
        pack_prompt,
        requirement,
        expectations,
        OUTPUT_CONTRACT,
    )
    return "\n\n".join(section.strip() for section in sections)


def prompt_version(text: str) -> str:
    """Return the first sixteen hexadecimal characters of the SHA-256 of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:VERSION_LENGTH]


def strip_code_fence(text: str) -> str:
    """Return the text without one leading and one trailing code fence.

    The opening fence may name a language. The two fence lines are removed and
    the code inside is kept as it is. Text that is not fenced, empty text
    included, is returned unchanged.
    """
    stripped = text.strip()
    if not stripped.startswith(FENCE) or not stripped.endswith(FENCE):
        return text
    lines = stripped.splitlines(keepends=True)
    if len(lines) < 2:
        return text
    if not _is_opening_fence(lines[0]) or not _is_closing_fence(lines[-1]):
        return text
    return "".join(lines[1:-1])


def _is_opening_fence(line: str) -> bool:
    """True when a line opens a code fence, with or without a language."""
    if not line.startswith(FENCE):
        return False
    label = line[len(FENCE):].strip()
    if not label:
        return True
    return not any(char.isspace() for char in label)


def _is_closing_fence(line: str) -> bool:
    """True when a line is a bare closing code fence."""
    return line.strip() == FENCE
