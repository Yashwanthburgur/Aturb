# Model API — verified

Provider: `nvidia` (NVIDIA-hosted models, OpenAI-compatible Chat Completions).
Base URL: `https://integrate.api.nvidia.com/v1`.
Endpoint path: `/chat/completions`.

Verified on 2026-11-21 against the live provider, with the key in the local
`.env`. Only the rows below were actually executed; nothing is copied from
provider documentation. A row marked **not verified** was not observed and must
not be used by client code.

## Configuration

| Setting  | Environment variable | Value                                        | Status   | Notes                                                                                                                                                                                                                         |
| -------- | -------------------- | -------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API key  | `NVIDIA_API_KEY`     | set in the local `.env`, never recorded here | Verified | Read by [`resolve_config()`](../../tools/spikes/model_call.py:62). The value is never printed and never leaves the machine.                                                                                                   |
| Base URL | `NVIDIA_BASE_URL`    | `https://integrate.api.nvidia.com/v1`        | Verified | The URL that answered.                                                                                                                                                                                                        |
| Model    | `NVIDIA_MODEL`       | `nvidia/nemotron-3.5-super-vl-120b-a12b`     | Verified | The model named by the local `.env` at the time of the verified call. The spike default is `minimaxai/minimax-m3.1-flash`, in [`DEFAULT_MODEL`](../../tools/spikes/model_call.py:31); that model was called too and answered. |

## Request, verified

| Call or behaviour                         | Purpose                                         | Verified in task | Notes                                                                                                                       |
| ----------------------------------------- | ----------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `POST {NVIDIA_BASE_URL}/chat/completions` | Send one non-streaming Chat Completions request | T5.03            | Answered **HTTP 200** with `Content-Type: application/json`.                                                                |
| Header `Authorization: Bearer <key>`      | Authenticate the request                        | T5.03            | Accepted. The key is replaced by a placeholder in every log and error by [`redact()`](../../tools/spikes/model_call.py:80). |
| Header `Content-Type: application/json`   | Declare the body format                         | T5.03            | Accepted.                                                                                                                   |
| Body field `model`                        | Name the model to call                          | T5.03            | Sent `nvidia/nemotron-3.5-super-vl-120b-a12b`.                                                                              |
| Body field `messages`                     | Carry the prompt                                | T5.03            | One user message, content `Reply with the single word: ok`.                                                                 |
| Body field `max_tokens`                   | Bound the answer                                | T5.03            | Sent `64`.                                                                                                                  |
| Body field `stream`                       | Keep the response non-streaming                 | T5.03            | Sent `false`; the answer came back as one JSON body.                                                                        |

## Response, verified

| Response field                                     | Purpose                                  | Verified in task | Notes                                                         |
| -------------------------------------------------- | ---------------------------------------- | ---------------- | ------------------------------------------------------------- |
| `choices[0].message.content`                       | Generated text                           | T5.03            | Held `"ok"`.                                                  |
| `usage.prompt_tokens`                              | Input token count                        | T5.03            | `23` on the spike call.                                       |
| `usage.completion_tokens`                          | Output token count                       | T5.03            | `63` on the spike call.                                       |
| `usage.total_tokens`                               | Total token count                        | T5.03            | `86` on the spike call.                                       |
| `usage.prompt_tokens_details.cached_tokens`        | Cached input tokens                      | T5.03            | `0` on the spike call.                                        |
| `usage.completion_tokens_details.reasoning_tokens` | Reasoning tokens inside the output count | T5.03            | `60` on the spike call.                                       |
| `id`                                               | Identifier of the completion             | T5.03            | `chatcmpl-<uuid>`.                                            |
| `object`                                           | Kind of the object                       | T5.03            | `"chat.completion"`.                                          |
| `created`                                          | Unix time of the completion              | T5.03            | `1795271131` on the spike call.                               |
| `model`                                            | Identifier of the model that answered    | T5.03            | See the model rows below.                                     |
| `choices[0].finish_reason`                         | Why the answer stopped                   | T5.03            | `"stop"`.                                                     |
| `choices[0].message.reasoning_content`             | Reasoning text beside the answer         | T5.03            | Present; the model returned its reasoning next to the answer. |
| `choices[0].message.refusal`                       | Refusal of the model                     | T5.03            | `null` on the spike call.                                     |
| `choices[0].index`                                 | Position of the choice                   | T5.03            | `0` on the spike call.                                        |
| `choices[0].logprobs`                              | Log probabilities of the choice          | T5.03            | `null` on the spike call.                                     |

Top-level keys of the answer: `choices`, `created`, `id`, `model`, `object`,
`usage`. Keys of `choices[0]`: `finish_reason`, `index`, `logprobs`, `message`.
Keys of `choices[0].message`: `content`, `reasoning_content`, `refusal`, `role`.

## The model identifier that answered

| Call or behaviour                                                                                          | Purpose                                           | Verified in task | Notes                                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Requested `nvidia/nemotron-3.5-super-vl-120b-a12b`, answered `private/nvidia/nemotron-3.5-super-120b-a12b` | Compare the requested model with the returned one | T5.03            | **They differ.** The returned identifier carries a `private/` prefix and no `-vl` segment. A client must not compare the two strings, and must not treat the returned identifier as the configured model. |
| Requested `minimaxai/minimax-m3.1-flash`, answered `minimaxai/minimax-m3.1-flash`                          | Compare the requested model with the returned one | T5.03            | The two strings are the same for this model.                                                                                                                                                              |

## Error responses

| Call or behaviour                                 | Purpose                        | Verified in task | Notes                                                                                                                                                                                                      |
| ------------------------------------------------- | ------------------------------ | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST {NVIDIA_BASE_URL}/completions` (wrong path) | Learn the shape of a 404       | T5.03            | **HTTP 404** with an **empty response body**. The status code is the only signal; there is no JSON error object to read.                                                                                   |
| HTTP 529                                          | Learn the shape of an overload | T5.03            | **Observed earlier in the session**, before the successful call. It was not reproduced afterwards — three further calls answered 200 — so **its response body is not recorded here and stays unverified**. |

## Still awaiting verification

- The response body of HTTP 529.
- Whether the provider accepts body fields other than `model`, `messages`,
  `max_tokens` and `stream`, and which of them are required.
- The behaviour of a request without `max_tokens`, and the largest accepted
  value.
- The behaviour of `stream: true`; the spike has no streaming support.
- The behaviour of a slow or cancelled request, and the timeout that the
  provider itself applies.
- The rate limits, the quota and the price of the tokens.
- Whether the returned `model` identifier is stable across calls for the same
  requested model.

## How to re-verify

1. Put the key in the local `.env`, which is Git-ignored: `NVIDIA_API_KEY=...`.
2. Run `uv run python tools/spikes/model_call.py` from the repository root.
3. The spike sends exactly one request and prints the request metadata, the
   response body and the observed field names. Exit code `0` means the call
   succeeded, `1` means the request failed, `2` means no key was configured and
   no request was sent.
4. Compare the printed fields with the tables above and update the rows that
   changed, keeping the task ID `T5.03`.
