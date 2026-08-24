"""
The model layer — one helper, two models, one SDK.

Both model calls in this app go through `litellm.completion`, so the extractor and
the adjudicator differ by a model string and a prompt, nothing else. That is the
whole reason a cheap/strong split is practical here: routing a mechanical step to
Haiku and a judgment step to Opus costs one argument, not a second client.

Structured output is done by prompting for JSON and validating with pydantic rather
than by a provider-specific structured-output mode. That keeps the pipeline honest
about failures (a malformed response is caught at the boundary and retried once)
and means swapping in a non-Anthropic model changes nothing but the model string.

Temperature is deliberately never passed — some Claude models reject it outright.
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

import litellm
from pydantic import BaseModel, ValidationError

import gateway

T = TypeVar("T", bound=BaseModel)

EXTRACTOR_MODEL = "anthropic/claude-haiku-4-5-20251001"
ADJUDICATOR_MODEL = "anthropic/claude-opus-5"

# Which of the app's two jobs each model does. In gateway mode the proxy is asked for
# the job by name instead, so this is also the mapping to config.yaml's model_list.
ROLES = {EXTRACTOR_MODEL: "extractor", ADJUDICATOR_MODEL: "adjudicator"}

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _first_json_object(text: str) -> str:
    """
    Pull the first complete JSON object out of a model response.

    Handles the three shapes that actually occur: a bare object, a fenced block, and
    an object preceded by a sentence of commentary.
    """
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1)

    start = text.find("{")
    if start == -1:
        return text

    depth, in_string, escaped = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def complete_json(
    model: str,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int = 8000,
) -> tuple[T, float]:
    """
    One model call that must return an object matching `schema`.

    Returns (validated object, response_cost). Retries once on malformed output,
    feeding the validation error back so the retry has something to correct.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    total_cost = 0.0
    last_error: Exception | None = None

    # Gateway mode swaps the provider model string for the proxy's alias. Everything
    # below is untouched by the switch, which is the point of routing through one SDK.
    call_model, extra = (
        gateway.completion_target(ROLES[model]) if gateway.ENABLED and model in ROLES else (model, {})
    )

    for attempt in (1, 2):
        response = litellm.completion(model=call_model, messages=messages, max_tokens=max_tokens, **extra)
        total_cost += float((getattr(response, "_hidden_params", None) or {}).get("response_cost") or 0.0)
        raw = response.choices[0].message.content or ""

        try:
            return schema.model_validate_json(_first_json_object(raw)), total_cost
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                break
            messages += [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        f"That did not validate against the required schema:\n{exc}\n\n"
                        "Return only the corrected JSON object. No commentary, no code fence."
                    ),
                },
            ]

    raise ValueError(f"{model} did not return valid {schema.__name__} after 2 attempts: {last_error}")
