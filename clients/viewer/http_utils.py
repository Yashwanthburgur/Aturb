"""The shared HTTP security and redaction helpers of the viewer client.

Every mutating endpoint of the viewer reads its body the same way: the local
host and the local origin are checked first, then the length of the body, and
only then the body itself. A refused request never reads the body.

The helpers live here so the three endpoint modules share one implementation
of the body limit, of the safe reading of a JSON body and of the redaction of
the credential of the environment.
"""

from __future__ import annotations

import json
import os
from email.message import Message
from io import BufferedIOBase

from aturb.agent.config import DEFAULTS
from aturb.agent.types import ModelClient, ModelRequest, ModelResponse

MAX_BODY_BYTES = 65_536  # starting default
REDACTED = "<redacted>"


class ApiError(Exception):
    """Raised when the endpoint answers with an error status."""

    def __init__(self, status: int, message: str) -> None:
        """Take the HTTP status and the message of the answer."""
        super().__init__(message)
        self.status = status
        self.message = message


class SafeModelClient:
    """A model client that keeps the credential out of every message.

    The core writes the error of a failed run into the manifest of the
    revision, so the credential is removed before the core ever sees it.
    """

    def __init__(self, client: ModelClient, secrets: tuple[str, ...]) -> None:
        """Take the client and the credential values that must not escape."""
        self._client = client
        self._secrets = secrets

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Answer with the client, or fail without the credential."""
        try:
            return self._client.complete(request)
        except Exception as exc:
            raise self._redacted(exc) from None

    def _redacted(self, exc: Exception) -> Exception:
        """Return the failure of the client without the credential in it."""
        message = str(exc)
        for secret in self._secrets:
            if secret:
                message = message.replace(secret, REDACTED)
        try:
            return type(exc)(message)
        except TypeError:
            return RuntimeError(message)


def read_content_length(headers: Message[str, str],
                        max_bytes: int = MAX_BODY_BYTES) -> int:
    """Return the length of the body, or refuse the request.

    A missing header is 411, a header that is not a number or is negative is
    400 and a body that is larger than the limit is 413. The body is never
    read here.
    """
    raw = headers.get("Content-Length")
    if raw is None:
        raise ApiError(411, "the request has no Content-Length header")
    try:
        length = int(raw.strip())
    except (AttributeError, ValueError):
        raise ApiError(
            400, "the Content-Length header is not a number") from None
    if length < 0:
        raise ApiError(400, "the Content-Length header is negative")
    if length > max_bytes:
        raise ApiError(413, "the request body is too large")
    return length


def read_json_object(headers: Message[str, str], rfile: BufferedIOBase,
                     max_bytes: int = MAX_BODY_BYTES) -> dict:
    """Read the body of one request and return the JSON object it holds."""
    length = read_content_length(headers, max_bytes)
    try:
        payload = json.loads(rfile.read(length).decode("utf-8"))
    except UnicodeDecodeError:
        raise ApiError(400, "the request body is not UTF-8") from None
    except ValueError:
        raise ApiError(400, "the request body is not JSON") from None
    if not isinstance(payload, dict):
        raise ApiError(400, "the request body is not a JSON object")
    return payload


def sanitize_message(text: str, settings: dict | None) -> str:
    """Return a message without a path of the host and without a credential.

    The measuring library is imported here and not at the top of the file, so
    that a viewer that never answers a request never loads it.
    """
    from aturb.evals.judge import sanitize_text

    cleaned = sanitize_text(text or "")
    for secret in configured_secrets(settings):
        if secret:
            cleaned = cleaned.replace(secret, REDACTED)
    return cleaned


def configured_secrets(settings: dict | None) -> tuple[str, ...]:
    """Return the credential values that must never reach the browser.

    The default name is read as well, so a configuration that cannot be read
    never leaks the credential of the environment.
    """
    names = {str(DEFAULTS.get("api_key_env", ""))}
    if settings is not None:
        names.add(str(settings.get("api_key_env", "")))
    return tuple(value for name in names if name
                 for value in [os.environ.get(name, "")] if value)
