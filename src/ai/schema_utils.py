"""
schema_utils.py
---------------
Resilient JSON schema validation and retry helper for AI modules.
Extracts JSON from model output, validates against a JSON schema,
retries once with feedback on invalid output, and falls back gracefully.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

import jsonschema

from ai.llm_client import LLMClient


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract a JSON object from raw LLM output, supporting markdown code fences
    or bare JSON strings.
    """
    text = text.strip()

    # 1. Check for markdown code fences: ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2. Check for outermost balanced curly braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass

    # 3. Direct parse attempt
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None


def query_structured_json(
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
    schema: Dict[str, Any],
    fallback_factory: Callable[[], Dict[str, Any]],
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """
    Query the LLM expecting a structured JSON response matching schema.
    If parsing or schema validation fails, retries once providing error feedback.
    Falls back gracefully if the retry also fails.
    """
    schema_str = json.dumps(schema, indent=2)
    augmented_system = (
        f"{system_prompt}\n\n"
        f"STRICT OUTPUT INSTRUCTION:\n"
        f"You must return ONLY a valid JSON object strictly conforming to this JSON schema:\n"
        f"{schema_str}\n"
        f"Do not include any introductory or concluding text outside the JSON."
    )

    messages = [
        {"role": "system", "content": augmented_system},
        {"role": "user", "content": user_prompt},
    ]

    # First Attempt
    try:
        response_text = client.generate(messages, temperature=temperature)
        data = extract_json_from_text(response_text)
        if data is not None:
            jsonschema.validate(instance=data, schema=schema)
            return data
        validation_err = "Output could not be parsed as a valid JSON object."
    except jsonschema.ValidationError as err:
        validation_err = f"Schema validation error: {err.message}"
    except Exception as exc:
        validation_err = f"Generation error: {exc}"

    # Retry Once with Validation Feedback
    retry_messages = list(messages)
    retry_messages.append({"role": "model", "content": response_text if "response_text" in locals() else ""})
    retry_messages.append(
        {
            "role": "user",
            "content": (
                f"Your previous output was invalid:\n{validation_err}\n\n"
                f"Please fix the error and output ONLY a valid JSON object strictly conforming to the schema:\n"
                f"{schema_str}"
            ),
        }
    )

    try:
        retry_response = client.generate(retry_messages, temperature=temperature)
        retry_data = extract_json_from_text(retry_response)
        if retry_data is not None:
            jsonschema.validate(instance=retry_data, schema=schema)
            return retry_data
    except Exception:
        pass

    # Graceful Fallback
    return fallback_factory()

