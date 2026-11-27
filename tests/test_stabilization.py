"""Tests for the stabilization card S1.

The card promises four things: a lazy startup, the parity of the configuration
flag of the viewer, one shared atomic persistence and one shared HTTP security.
Every test here stays on the machine: no test calls a model and no test opens
a connection that leaves the loopback address.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from argparse import Namespace
from email.message import Message
from io import BytesIO
from pathlib import Path

import pytest

from aturb.agent.types import ModelRequest, ModelResponse
from aturb.config import load_config
from aturb.workspace.io import atomic_copy, atomic_write_text
from clients.viewer.http_utils import (
    MAX_BODY_BYTES,
    ApiError,
    SafeModelClient,
    read_content_length,
    read_json_object,
    sanitize_message,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HEAVY_MODULES = ("OCP", "build123d", "numpy", "scipy", "sklearn")


def _heavy_modules_after_import(module: str) -> list[str]:
    """Return the heavy modules that the import of one module loaded."""
    code = (
        "import json, sys\n"
        f"import {module}\n"
        f"heavy = {HEAVY_MODULES!r}\n"
        "print(json.dumps([name for name in heavy if name in sys.modules]))\n"
    )
    finished = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True,
        text=True, check=True)
    return json.loads(finished.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("module", ["aturb.cli", "clients.viewer.cli"])
def test_the_command_line_loads_no_heavy_module(module):
    """Importing a command line loads no heavy module."""
    assert _heavy_modules_after_import(module) == []


def _workspace(root: Path) -> Path:
    """Write a minimal workspace with a manifest and return its folder."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "result.toml").write_text(
        'status = "ok"\npart_id = "part0001"\nstop_reason = "built"\n',
        encoding="utf-8")
    return root


def _config(path: Path, pack: str) -> Path:
    """Write a configuration file that names one pack and return its path."""
    path.write_text(
        f'active_pack = "{pack}"\n\n'
        "[timeouts]\nbuild_s = 60\n\n"
        "[agent]\nprovider = \"openai_compatible\"\nmodel = \"test-model\"\n"
        "base_url = \"http://127.0.0.1:1/v1\"\n"
        "api_key_env = \"ATURB_STABILIZATION_KEY\"\n",
        encoding="utf-8")
    return path


def _viewer(tmp_path: Path, config: Path | None):
    """Start a viewer on a free port and return the server it bound."""
    from clients.viewer.cli import run_view_command, start_viewer

    workspace = _workspace(tmp_path / "workspace")
    captured: dict[str, object] = {}

    def factory(workspace_path: Path, config_path: Path | None = None):
        server = start_viewer(workspace_path, port=0, config_path=config_path)
        captured["server"] = server
        return server

    args = Namespace(workspace=str(workspace),
                     config=str(config) if config is not None else None)
    code = run_view_command(args, server_factory=factory,
                            serve_fn=lambda server: None)
    assert code == 0
    return captured["server"]


def test_the_view_command_gives_the_configuration_to_every_service(tmp_path):
    """The --config flag reaches the three services of the viewer."""
    config = _config(tmp_path / "custom.toml", "stub")
    server = _viewer(tmp_path, config)
    generate = server.generate_handler
    edit = server.edit_handler.__self__
    assembly = server.assembly_edit_service
    assert generate._config_path == config
    assert edit._config_path == config
    assert assembly._config_path == config
    assert generate._load_config()["active_pack"] == "stub"
    assert edit._load_config()["active_pack"] == "stub"
    assert load_config(assembly._config_path)["active_pack"] == "stub"


def test_the_view_command_without_a_configuration_uses_the_default(tmp_path):
    """Without the flag every service keeps the default of the machine."""
    server = _viewer(tmp_path, None)
    assert server.generate_handler._config_path is None
    assert server.edit_handler.__self__._config_path is None
    assert server.assembly_edit_service._config_path is None


def test_the_atomic_write_replaces_the_file_and_leaves_no_temporary(tmp_path):
    """The write replaces the file and leaves no temporary file behind."""
    target = tmp_path / "nested" / "note.txt"
    atomic_write_text(target, "first\n")
    atomic_write_text(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"
    assert [item.name for item in target.parent.iterdir()] == ["note.txt"]


def test_the_atomic_copy_copies_the_bytes_and_leaves_no_temporary(tmp_path):
    """The copy writes the bytes and leaves no temporary file behind."""
    source = tmp_path / "source.txt"
    source.write_text("payload\n", encoding="utf-8")
    target = tmp_path / "copy" / "target.txt"
    atomic_copy(source, target)
    assert target.read_text(encoding="utf-8") == "payload\n"
    assert [item.name for item in target.parent.iterdir()] == ["target.txt"]


def test_a_failed_atomic_write_keeps_the_old_file_and_cleans_up(tmp_path,
                                                                monkeypatch):
    """A failure keeps the old file and removes the temporary file."""
    target = tmp_path / "note.txt"
    target.write_text("old\n", encoding="utf-8")

    def refuse(source_path, destination):
        raise OSError("the disk is full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert [item.name for item in tmp_path.iterdir()] == ["note.txt"]


def test_a_failed_atomic_copy_keeps_the_old_file_and_cleans_up(tmp_path,
                                                               monkeypatch):
    """A failed copy keeps the old file and removes the temporary file."""
    source = tmp_path / "source.txt"
    source.write_text("payload\n", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("old\n", encoding="utf-8")

    def refuse(source_path, destination):
        raise OSError("the disk is full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        atomic_copy(source, target)
    assert target.read_text(encoding="utf-8") == "old\n"
    assert sorted(item.name for item in tmp_path.iterdir()) == [
        "source.txt", "target.txt"]


def _headers(length: str | None) -> Message:
    """Return the headers of one request with the given body length."""
    headers = Message()
    if length is not None:
        headers["Content-Length"] = length
    return headers


@pytest.mark.parametrize("length,status", [
    (None, 411),
    ("abc", 400),
    ("-1", 400),
    (str(MAX_BODY_BYTES + 1), 413),
])
def test_the_body_limit_refuses_the_request_before_reading_it(length, status):
    """A refused request is refused on its header, without reading the body."""
    with pytest.raises(ApiError) as excinfo:
        read_content_length(_headers(length))
    assert excinfo.value.status == status


def test_the_body_limit_accepts_exactly_the_limit():
    """A body of exactly the limit is accepted."""
    assert MAX_BODY_BYTES == 65_536
    assert read_content_length(_headers(str(MAX_BODY_BYTES))) == MAX_BODY_BYTES


def test_the_json_reader_takes_the_limit_and_refuses_one_byte_more():
    """The JSON reader takes the limit and refuses one byte more."""
    empty = json.dumps({"instruction": ""})
    payload = {"instruction": "x" * (MAX_BODY_BYTES - len(empty))}
    body = json.dumps(payload).encode("utf-8")
    assert len(body) == MAX_BODY_BYTES
    assert read_json_object(_headers(str(len(body))), BytesIO(body)) == payload
    with pytest.raises(ApiError) as excinfo:
        read_json_object(_headers(str(MAX_BODY_BYTES + 1)), BytesIO(b"{}"))
    assert excinfo.value.status == 413


def test_every_endpoint_module_uses_the_same_body_limit():
    """The three endpoint modules share one body limit."""
    from clients.viewer import assembly_edit_api, edit_api, generate_api

    assert generate_api.MAX_BODY_BYTES == MAX_BODY_BYTES
    assert edit_api.MAX_BODY_BYTES == MAX_BODY_BYTES
    assert assembly_edit_api.MAX_BODY_BYTES == MAX_BODY_BYTES


class _FailingClient:
    """A client that always fails with the credential in the message."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Fail with a message that holds the credential."""
        raise RuntimeError("the provider refused the key sk-secret-value")


class _AnsweringClient:
    """A client that answers with one canned text."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with one canned text."""
        return ModelResponse("the answer", 3, 4)


def test_the_safe_client_keeps_the_credential_out_of_the_message():
    """The credential never reaches the message of the failure."""
    client = SafeModelClient(_FailingClient(), ("sk-secret-value",))
    with pytest.raises(RuntimeError) as excinfo:
        client.complete(ModelRequest("the prompt", "the model", 10))
    assert "sk-secret-value" not in str(excinfo.value)
    assert "<redacted>" in str(excinfo.value)


def test_the_safe_client_passes_the_answer_of_the_client_through():
    """A successful answer is not changed by the safe client."""
    client = SafeModelClient(_AnsweringClient(), ("sk-secret-value",))
    answer = client.complete(ModelRequest("the prompt", "the model", 10))
    assert answer.text == "the answer"


def test_the_message_of_the_viewer_keeps_the_credential_out(monkeypatch):
    """The message of the viewer never holds the credential."""
    monkeypatch.setenv("ATURB_STABILIZATION_KEY", "sk-secret-value")
    message = sanitize_message(
        "the key sk-secret-value failed",
        {"api_key_env": "ATURB_STABILIZATION_KEY"})
    assert "sk-secret-value" not in message
    assert "<redacted>" in message
