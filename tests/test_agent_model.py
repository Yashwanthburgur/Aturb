"""Tests for the model client.

The client is tested with fake transports, so no test touches the network. The
tests check the request body the API notes record, the response the client
reads out of the answer, and the errors it raises when the call does not work.
"""

from __future__ import annotations

import json
import urllib.error
from email.message import Message
from io import BytesIO
from typing import Any

import pytest

from aturb.agent.model import HttpModelClient, http_transport
from aturb.agent.types import AgentError, ModelRequest

API_KEY = "test-key-must-not-be-logged"
BASE_URL = "https://example.invalid/v1"
MODEL = "some-model-id"
PROMPT = "Write one part file."


def _request(model: str = MODEL, max_output_tokens: int = 256) -> ModelRequest:
    """Return a model request for the tests."""
    return ModelRequest(prompt=PROMPT, model=model, max_output_tokens=max_output_tokens)


def _answer(text: str = "the answer", input_tokens: int = 12, output_tokens: int = 7) -> str:
    """Return a response body that holds the fields the API notes record."""
    return json.dumps({
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    })


class _FakeTransport:
    """A transport that records the call and returns a canned answer."""

    def __init__(self, answer: str) -> None:
        """Take the answer the transport returns."""
        self.answer = answer
        self.calls: list[tuple[str, dict[str, Any],
                               dict[str, str], float]] = []

    def __call__(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> str:
        """Record the call and return the canned answer."""
        self.calls.append((url, body, headers, timeout))
        return self.answer


def _failing_transport(failure: Exception):
    """Return a transport that always fails with the given error."""

    def transport(
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> str:
        raise failure

    return transport


def _http_error() -> urllib.error.HTTPError:
    """Return the error of a non-success status."""
    return urllib.error.HTTPError(
        f"{BASE_URL}/chat/completions", 401, "Unauthorized", Message(), BytesIO(b"")
    )


def _client(transport, **overrides) -> HttpModelClient:
    """Return a client with a fake transport."""
    settings: dict[str, Any] = {
        "base_url": BASE_URL,
        "model": MODEL,
        "api_key": API_KEY,
        "timeout": 5.0,
        "transport": transport,
    }
    settings.update(overrides)
    return HttpModelClient(**settings)


def test_a_good_response_becomes_a_model_response():
    """A response with the recorded fields becomes a model response."""
    client = _client(_FakeTransport(_answer()))

    response = client.complete(_request())

    assert response.text == "the answer"
    assert response.input_tokens == 12
    assert response.output_tokens == 7


def test_the_request_body_holds_the_recorded_fields():
    """The body holds the fields the API notes record, and nothing else."""
    transport = _FakeTransport(_answer())
    client = _client(transport)

    client.complete(_request())

    _, body, _, _ = transport.calls[0]
    assert set(body) == {"model", "messages", "max_tokens", "stream"}
    assert body["model"] == MODEL
    assert body["messages"] == [{"role": "user", "content": PROMPT}]
    assert body["max_tokens"] == 256
    assert body["stream"] is False


def test_the_request_goes_to_the_configured_endpoint():
    """The URL is the base URL and the endpoint of the configuration."""
    transport = _FakeTransport(_answer())
    client = _client(transport)

    client.complete(_request())

    url, _, headers, timeout = transport.calls[0]
    assert url == f"{BASE_URL}/chat/completions"
    assert headers["Authorization"] == f"Bearer {API_KEY}"
    assert headers["Content-Type"] == "application/json"
    assert timeout == 5.0


def test_the_endpoint_is_configurable():
    """A different endpoint is used when the configuration names one."""
    transport = _FakeTransport(_answer())
    client = _client(transport, endpoint="/v2/chat/completions")

    client.complete(_request())

    url, _, _, _ = transport.calls[0]
    assert url == f"{BASE_URL}/v2/chat/completions"


def test_the_model_of_the_request_wins():
    """The model of the request is the one that is sent."""
    transport = _FakeTransport(_answer())
    client = _client(transport)

    client.complete(_request(model="another-model-id"))

    _, body, _, _ = transport.calls[0]
    assert body["model"] == "another-model-id"


def test_the_configured_model_is_the_fallback():
    """A request without a model uses the model of the client."""
    transport = _FakeTransport(_answer())
    client = _client(transport)

    client.complete(_request(model=""))

    _, body, _, _ = transport.calls[0]
    assert body["model"] == MODEL


def test_the_default_transport_is_the_http_one():
    """A client without a transport talks to the provider over urllib."""
    client = HttpModelClient(BASE_URL, MODEL, API_KEY, 5.0)

    assert client.transport is http_transport


def test_a_response_without_text_raises():
    """A response without the generated text is refused."""
    body = json.dumps({
        "choices": [{"message": {"role": "assistant"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    })
    client = _client(_FakeTransport(body))

    with pytest.raises(AgentError) as excinfo:
        client.complete(_request())

    assert "text" in str(excinfo.value)


def test_a_response_without_choices_raises():
    """A response without any choice is refused."""
    body = json.dumps({"usage": {"prompt_tokens": 12, "completion_tokens": 7}})
    client = _client(_FakeTransport(body))

    with pytest.raises(AgentError):
        client.complete(_request())


def test_a_response_without_token_usage_raises():
    """A response without the token usage is refused."""
    body = json.dumps({"choices": [{"message": {"content": "the answer"}}]})
    client = _client(_FakeTransport(body))

    with pytest.raises(AgentError) as excinfo:
        client.complete(_request())

    assert "usage" in str(excinfo.value)


@pytest.mark.parametrize(
    "usage",
    [{"completion_tokens": 7}, {"prompt_tokens": 12}],
)
def test_a_response_without_a_token_count_raises(usage):
    """A response without one of the token counts is refused."""
    body = json.dumps({
        "choices": [{"message": {"content": "the answer"}}],
        "usage": usage,
    })
    client = _client(_FakeTransport(body))

    with pytest.raises(AgentError):
        client.complete(_request())


def test_a_response_that_is_not_json_raises():
    """A response that is not JSON is refused."""
    client = _client(_FakeTransport("not json at all"))

    with pytest.raises(AgentError):
        client.complete(_request())


def test_a_non_success_status_raises():
    """A non-success status is refused and the status is in the message."""
    client = _client(_failing_transport(_http_error()))

    with pytest.raises(AgentError) as excinfo:
        client.complete(_request())

    assert "401" in str(excinfo.value)


def test_a_timeout_raises():
    """A timeout is refused and the message says so."""
    client = _client(_failing_transport(TimeoutError("timed out")))

    with pytest.raises(AgentError) as excinfo:
        client.complete(_request())

    assert "timed out" in str(excinfo.value)


def test_a_transport_failure_raises():
    """A transport that fails is refused and the reason is in the message."""
    client = _client(_failing_transport(RuntimeError("the socket went away")))

    with pytest.raises(AgentError) as excinfo:
        client.complete(_request())

    assert "the socket went away" in str(excinfo.value)


def test_the_client_calls_the_transport_once():
    """One request is one call of the transport."""
    transport = _FakeTransport(_answer())
    client = _client(transport)

    client.complete(_request())

    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "failure",
    [
        _http_error(),
        TimeoutError("timed out"),
        RuntimeError("the socket went away"),
        RuntimeError(f"the key {API_KEY} was refused"),
    ],
)
def test_the_api_key_is_in_no_error_message(failure):
    """No error message carries the API key."""
    client = _client(_failing_transport(failure))

    with pytest.raises(AgentError) as excinfo:
        client.complete(_request())

    assert API_KEY not in str(excinfo.value)
