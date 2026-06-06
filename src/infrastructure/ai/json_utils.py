"""Utilities for robustly parsing model JSON responses."""

from __future__ import annotations

import json
import re
from typing import Any

from src.domain.exceptions import AIServiceError


def parse_json_object(raw: str, context: str) -> dict[str, Any]:
    """Parse a model response into a JSON object, tolerating common output noise."""
    candidates = _candidate_json_strings(raw)

    for candidate in candidates:
        payload = _try_parse_json(candidate)
        if isinstance(payload, dict):
            return payload

    # Last attempt: parse first balanced JSON object from the original text.
    balanced = _first_balanced_object(raw)
    if balanced:
        payload = _try_parse_json(balanced)
        if isinstance(payload, dict):
            return payload

    snippet = raw if len(raw) <= 800 else f"{raw[:800]}..."
    raise AIServiceError(f"{context} response is not valid JSON: {snippet!r}")


def _try_parse_json(text: str) -> Any:
    candidate = text.strip()
    if not candidate:
        return None

    for _ in range(3):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        if isinstance(parsed, str):
            candidate = parsed.strip()
            continue
        return parsed

    return None


def _candidate_json_strings(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []

    candidates: list[str] = [text]

    # JSON fenced blocks.
    for block in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE):
        block = block.strip()
        if block:
            candidates.append(block)

    # Leading/trailing chatter before/after the JSON object.
    balanced = _first_balanced_object(text)
    if balanced:
        candidates.append(balanced)

    return candidates


def _first_balanced_object(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return text[start : start + end]

    return None
