"""One-shot Chat Completions spike for the NVIDIA-hosted MiniMax model.

The spike reads ``NVIDIA_API_KEY``, ``NVIDIA_BASE_URL`` and ``NVIDIA_MODEL``
from the local ``.env`` file. A process environment variable of the same name
wins over the file. The script sends exactly one non-streaming Chat Completions
request, prints the request metadata and the response, and never prints the
API key.

Run it from the repository root:

    uv run python tools/spikes/model_call.py

Exit codes: 0 the call succeeded, 1 the call failed, 2 the configuration is
incomplete (no API key), in which case no request is sent.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"  # starting default
DEFAULT_MODEL = "minimaxai/minimax-m3.1-flash"  # starting default
ENDPOINT_PATH = "/chat/completions"
PROMPT = "Reply with the single word: ok"
MAX_TOKENS = 64  # starting default
TIMEOUT_S = 60  # starting default
REDACTED = "<redacted>"


def load_env_file(path: Path) -> dict[str, str]:
    """Read the KEY=VALUE pairs of a .env file. The values are never printed."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name:
            values[name] = value
    return values


def resolve_config(env_file: Path) -> dict[str, str]:
    """Return the three settings, from the environment first and the file second."""
    file_values = load_env_file(env_file)
    config: dict[str, str] = {}
    for name, fallback in (
        ("NVIDIA_API_KEY", ""),
        ("NVIDIA_BASE_URL", DEFAULT_BASE_URL),
        ("NVIDIA_MODEL", DEFAULT_MODEL),
    ):
        value = os.environ.get(name, "").strip()
        if not value:
            value = file_values.get(name, "").strip()
        if not value:
            value = fallback
        config[name] = value
    return config


def redact(text: str, secret: str) -> str:
    """Replace every occurrence of the API key with a placeholder."""
    if not secret:
        return text
    return text.replace(secret, REDACTED)


def build_url(base_url: str) -> str:
    """Join the base URL and the Chat Completions endpoint path."""
    return base_url.rstrip("/") + ENDPOINT_PATH


def build_request_body(model: str) -> dict[str, Any]:
    """Build the non-streaming Chat Completions body sent by this spike."""
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }


def request_metadata(url: str, body: dict[str, Any]) -> str:
    """Describe the request without the credential."""
    lines = [
        "method: POST",
        f"url: {url}",
        "headers:",
        f"  Authorization: Bearer {REDACTED}",
        "  Content-Type: application/json",
        "  Accept: application/json",
        "body:",
        json.dumps(body, indent=2, sort_keys=True),
    ]
    return "\n".join(lines)


def describe_response(payload: Any) -> list[str]:
    """List the field names the response actually carries."""
    if not isinstance(payload, dict):
        return [f"response body type: {type(payload).__name__}"]
    lines = [f"top-level keys: {sorted(payload.keys())}"]
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        lines.append(f"choices[0] keys: {sorted(choices[0].keys())}")
        message = choices[0].get("message")
        if isinstance(message, dict):
            lines.append(f"choices[0].message keys: {sorted(message.keys())}")
    usage = payload.get("usage")
    if isinstance(usage, dict):
        lines.append(f"usage keys: {sorted(usage.keys())}")
    return lines


def main() -> int:
    """Send one request and print what was sent and what came back."""
    config = resolve_config(ENV_FILE)
    api_key = config["NVIDIA_API_KEY"]
    url = build_url(config["NVIDIA_BASE_URL"])
    body = build_request_body(config["NVIDIA_MODEL"])

    print("== request ==")
    print(request_metadata(url, body))

    if not api_key:
        print()
        print("model_call: NVIDIA_API_KEY is not set, so no request was sent.")
        print("model_call: the real API call is pending until the key is supplied.")
        return 2

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        content_type = exc.headers.get(
            "Content-Type", "") if exc.headers else ""
        raw = exc.read().decode("utf-8", errors="replace")
        print()
        print("== response ==")
        print(f"status: {status}")
        print(f"content-type: {content_type}")
        print("body:")
        print(redact(raw, api_key))
        print()
        print("model_call: the request failed, so the API contract was not verified.")
        return 1
    except urllib.error.URLError as exc:
        print()
        print(
            f"model_call: the request failed: {redact(str(exc.reason), api_key)}")
        return 1
    except TimeoutError:
        print()
        print(f"model_call: the request timed out after {TIMEOUT_S} s.")
        return 1
    except OSError as exc:
        print()
        print(f"model_call: the request failed: {redact(str(exc), api_key)}")
        return 1

    print()
    print("== response ==")
    print(f"status: {status}")
    print(f"content-type: {content_type}")
    print("body:")
    print(redact(raw, api_key))

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print()
        print(
            "model_call: the response body is not JSON, so the contract was not verified.")
        return 1

    print()
    print("== observed fields ==")
    for line in describe_response(payload):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
