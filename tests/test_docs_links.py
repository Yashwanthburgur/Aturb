"""The link integrity of the documentation.

Every relative link of the documentation must point at a file that exists. The
scanner strips the fenced code blocks and the inline code spans first, and it
reads the inline links, the image links and the reference-style links. A target
inside a git-ignored folder is not a file of the repository and is not checked.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from aturb.agent.config import agent_settings
from aturb.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("docs", "aturb", "clients")
EXTERNAL = ("http://", "https://", "mailto:")
LINE_SUFFIX = re.compile(r":\d+(?:-L?\d+)?$")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"`+[^`]*`+")
INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
REFERENCE_DEF = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(\S+)")
REFERENCE_USE = re.compile(r"!?\[([^\]]*)\]\[([^\]]*)\]")
IGNORED = tuple(
    line.strip()
    for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if line.strip().endswith("/") and not line.strip().startswith("#")
)


def _sources() -> list[Path]:
    """Return the markdown files the scanner reads."""
    files = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md"]
    for root in SCAN_ROOTS:
        files.extend(sorted((REPO_ROOT / root).rglob("*.md")))
    return files


def _strip_fences(text: str) -> str:
    """Return the text without its fenced code blocks, with the line numbers kept."""
    kept: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence is None and match:
            fence = match.group(1)
        elif (fence is not None and match
              and match.group(1)[0] == fence[0]
              and len(match.group(1)) >= len(fence)):
            fence = None
        kept.append("" if fence is not None or match else line)
    return "\n".join(kept)


def _scan(path: Path) -> list[tuple[int, str]]:
    """Return the (line, target) pairs of every link of one markdown file."""
    lines = _strip_fences(path.read_text(encoding="utf-8")).splitlines()
    definitions: dict[str, str] = {}
    for raw in lines:
        match = REFERENCE_DEF.match(INLINE_CODE.sub("", raw))
        if match:
            definitions[match.group(1).strip().lower()] = match.group(2)
    found: list[tuple[int, str]] = []
    for number, raw in enumerate(lines, start=1):
        line = INLINE_CODE.sub("", raw)
        if REFERENCE_DEF.match(line):
            continue
        found.extend((number, match.group(1))
                     for match in INLINE_LINK.finditer(line))
        for match in REFERENCE_USE.finditer(line):
            key = (match.group(2) or match.group(1)).strip().lower()
            if key in definitions:
                found.append((number, definitions[key]))
    return found


def _resolve(source: Path, target: str) -> Path | None:
    """Return the path a link target names, or None when it names no file."""
    text = target.strip()
    if not text or text.startswith("#") or text.lower().startswith(EXTERNAL):
        return None
    if text.startswith("<"):
        end = text.find(">")
        text = text[1:end] if end != -1 else text[1:]
    else:
        text = text.split(None, 1)[0] if text else ""
    text = LINE_SUFFIX.sub("", text.split("#", 1)[0])
    return (source.parent / unquote(text)).resolve() if text else None


def _is_ignored(path: Path) -> bool:
    """True when the path lies inside a folder that is not committed."""
    relative = path.relative_to(REPO_ROOT).as_posix(
    ) if path.is_relative_to(REPO_ROOT) else ""
    return any(relative.startswith(prefix) for prefix in IGNORED)


def test_the_scanner_ignores_the_code_of_a_file(tmp_path):
    """A path inside a code span or a fenced block is not a link."""
    source = tmp_path / "note.md"
    source.write_text(
        "text `[inline](missing.md)`\n\n```text\n[fenced](missing.md)\n```\n\n"
        "[real](present.md)\n",
        encoding="utf-8")
    assert [target for _, target in _scan(source)] == ["present.md"]


def test_the_scanner_reads_the_links_of_the_readme():
    """The scanner finds the links of the readme."""
    targets = [target for _, target in _scan(REPO_ROOT / "README.md")]
    assert "docs/ARCHITECTURE.md" in targets
    assert "AGENTS.md" in targets


def test_every_relative_link_of_the_documentation_resolves():
    """Every relative link of the documentation points at a file that exists."""
    broken: list[str] = []
    for source in _sources():
        for number, target in _scan(source):
            resolved = _resolve(source, target)
            if resolved is None or _is_ignored(resolved):
                continue
            if not resolved.exists():
                name = source.relative_to(REPO_ROOT).as_posix()
                broken.append(f"{name}:{number} -> {target}")
    assert not broken, "unresolved links:\n" + "\n".join(broken)


def test_the_example_configuration_loads_and_gives_the_agent_settings():
    """The example configuration parses and yields the agent settings."""
    cfg = load_config(REPO_ROOT / "aturb.example.toml")
    settings = agent_settings(cfg)
    assert settings["max_attempts"] == 3
    assert settings["max_total_cost_usd"] == 0.75
    assert settings["max_total_input_tokens"] == 60000
    assert settings["max_total_output_tokens"] == 24000
    assert settings["api_key_env"] == "ATURB_AGENT_API_KEY"
