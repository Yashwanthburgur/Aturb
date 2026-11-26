"""The model client: one request in, one response out.

The client makes the call recorded in
[`docs/api_notes/model.md`](../../docs/api_notes/model.md): a non-streaming
Chat Completions request, and a response that carries the generated text and
the two token counts. It reads only the fields that note records, it never
retries, and it never puts the API key in an error message.

The reasoning effort is the one optional field of the request body. It is sent
only when the configuration names one, so a request without one is exactly the
request that was sent before.

The transport is a parameter, so the tests never touch the network. The default
transport is the one that talks to the provider over `urllib.request`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

from aturb.agent.types import AgentError, ModelRequest, ModelResponse

CHAT_COMPLETIONS_PATH = "/chat/completions"
REDACTED = "<redacted>"

Transport = Callable[[str, dict[str, Any], dict[str, str], float], str]


def http_transport(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> str:
    """Send one request with urllib and return the response text."""
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


class HttpModelClient:
    """A client that turns one model request into one model response.

    The base URL, the model, the endpoint and the provider are configuration,
    not code: nothing here names a particular model. The model of the request
    wins over the model of the client, so one client can serve one run.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 60.0,  # starting default
        transport: Transport | None = None,
        *,
        endpoint: str = CHAT_COMPLETIONS_PATH,  # starting default
        provider: str = "",  # starting default
        reasoning_effort: str = "",  # starting default
    ) -> None:
        """Take the configuration of the call and the transport that makes it."""
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.transport: Transport = transport if transport is not None else http_transport
        self.endpoint = endpoint
        self.provider = provider
        self.reasoning_effort = reasoning_effort

    @classmethod
    def from_settings(
        cls,
        settings: dict,
        api_key: str,
        *,
        transport: Transport | None = None,
        timeout: float | None = None,
    ) -> "HttpModelClient":
        """Build a client from the agent settings of a configuration.

        The settings name the base URL, the model, the timeout, the provider
        and the optional reasoning effort. The API key is never read from the
        settings: it comes from the environment variable they name.
        """
        return cls(
            base_url=str(settings["base_url"]),
            model=str(settings["model"]),
            api_key=api_key,
            timeout=float(settings["timeout_s"]
                          ) if timeout is None else timeout,
            transport=transport,
            provider=str(settings["provider"]),
            reasoning_effort=str(settings.get("reasoning_effort", "")),
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Send one request to the model and return its response."""
        url = self.base_url.rstrip("/") + self.endpoint
        body = self._request_body(request)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            text = self.transport(url, body, headers, self.timeout)
        except urllib.error.HTTPError as exc:
            raise AgentError(
                self._safe(
                    f"{self._label()} request failed with HTTP status {exc.code}: {exc.reason}")
            ) from None
        except TimeoutError:
            raise AgentError(
                self._safe(
                    f"{self._label()} request timed out after {self.timeout} s")
            ) from None
        except urllib.error.URLError as exc:
            raise AgentError(
                self._safe(f"{self._label()} request failed: {exc.reason}")
            ) from None
        except AgentError as exc:
            raise AgentError(self._safe(str(exc))) from None
        except Exception as exc:
            raise AgentError(
                self._safe(f"{self._label()} request failed: {exc}")
            ) from None
        return self._parse_response(text)

    def _request_body(self, request: ModelRequest) -> dict[str, Any]:
        """Build the request body recorded in the API notes.

        The reasoning effort is optional: it is sent only when the
        configuration names one, so a request without one carries exactly the
        fields it carried before.
        """
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return body

    def _parse_response(self, text: str) -> ModelResponse:
        """Read the generated text and the token counts out of the response."""
        try:
            payload = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise AgentError(
                self._safe(f"the {self._label()} response is not JSON: {exc}")
            ) from None
        if not isinstance(payload, dict):
            raise AgentError(
                f"the {self._label()} response is not a JSON object")
        answer = _response_text(payload)
        if not answer:
            raise AgentError(self._empty_text_error(payload))
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise AgentError(
                f"the {self._label()} response has no token usage")
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        if not _is_count(input_tokens):
            raise AgentError(
                f"the {self._label()} response has no input token count")
        if not _is_count(output_tokens):
            raise AgentError(
                f"the {self._label()} response has no output token count")
        return ModelResponse(
            text=answer,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _label(self) -> str:
        """Return the name of the provider for the error messages."""
        return f"{self.provider} model" if self.provider else "model"

    def _safe(self, message: str) -> str:
        """Replace the API key in a message with a placeholder."""
        if not self.api_key:
            return message
        return message.replace(self.api_key, REDACTED)

    def _empty_text_error(self, payload: dict[str, Any]) -> str:
        """Explain an empty answer when the response says why it is empty."""
        first = _first_choice(payload)
        message = first.get("message")
        message = message if isinstance(message, dict) else {}
        finish = first.get("finish_reason")
        reasoning = message.get(
            "reasoning_content") or message.get("reasoning")
        has_reasoning = isinstance(reasoning, str) and bool(reasoning.strip())
        if finish != "length" and not has_reasoning:
            return f"the {self._label()} response has no generated text"
        usage = payload.get("usage")
        tokens = usage.get("completion_tokens") if isinstance(
            usage, dict) else None
        suffix = f" (completion_tokens={tokens})" if _is_count(tokens) else ""
        if finish == "length":
            return (f"the {self._label()} response hit the output-token limit "
                    f"(finish_reason=length) during reasoning before emitting "
                    f"final text{suffix}")
        return (f"the {self._label()} response ended during reasoning before "
                f"emitting final text (finish_reason={finish or 'unknown'}){suffix}")


def _first_choice(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the first choice object, or an empty object when it is absent."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    return first if isinstance(first, dict) else {}


def _response_text(payload: dict[str, Any]) -> str | None:
    """Return the generated text, or None when the response does not hold it."""
    first = _first_choice(payload)
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return content


def _is_count(value: Any) -> bool:
    """Return True when a value is a whole number of tokens."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
