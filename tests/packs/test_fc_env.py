"""The child process environment must never carry secrets."""

from __future__ import annotations

from packs.freecad.runner import child_env


def test_child_env_filters_secrets(tmp_path):
    """Only allowed keys plus ATURB_REQUEST survive."""
    base = {
        "PATH": "C:/Windows",
        "OPENAI_API_KEY": "sk-secret",
        "HTTPS_PROXY": "http://proxy",
        "MY_TOKEN": "token",
        "SECRET_X": "x",
    }
    job = tmp_path / "job.json"
    env = child_env(base, job)
    assert env["PATH"] == "C:/Windows"
    assert env["ATURB_REQUEST"] == str(job)
    for key in ("OPENAI_API_KEY", "HTTPS_PROXY", "MY_TOKEN", "SECRET_X"):
        assert key not in env
