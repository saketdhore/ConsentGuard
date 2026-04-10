"""Minimal OpenAI Responses API client for structured document generation."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


class OpenAIProviderError(RuntimeError):
    """Raised when the OpenAI provider cannot return structured JSON."""


class OpenAIProvider:
    """Thin wrapper around the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate_structured_json(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        json_schema: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Request a structured JSON response from the OpenAI Responses API."""

        if not self.api_key:
            raise OpenAIProviderError(
                "OPENAI_API_KEY is not configured for OpenAI document generation."
            )

        payload = {
            "model": model or self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": instructions}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_text}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                }
            },
        }

        try:
            http_request = request.Request(
                url=f"{self.base_url}/responses",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(
                http_request, timeout=self.timeout_seconds
            ) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            try:
                error_payload = json.loads(exc.read().decode("utf-8"))
                error_message = error_payload.get("error", {}).get("message")
            except Exception:
                error_message = None
            raise OpenAIProviderError(
                error_message or f"OpenAI request failed with status {exc.code}."
            ) from exc
        except error.URLError as exc:
            raise OpenAIProviderError(
                f"OpenAI request failed: {exc}"
            ) from exc

        try:
            response_data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise OpenAIProviderError("OpenAI response was not valid JSON.") from exc

        if not isinstance(response_data, dict):
            raise OpenAIProviderError("OpenAI response body must be a JSON object.")

        if isinstance(response_data.get("error"), dict):
            message = response_data["error"].get("message", "Unknown OpenAI API error.")
            raise OpenAIProviderError(message)

        raw_output = self._extract_output_text(response_data)
        if raw_output is None:
            raise OpenAIProviderError(
                "OpenAI response did not include structured output text."
            )

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise OpenAIProviderError(
                "OpenAI structured output was not valid JSON."
            ) from exc

        if not isinstance(parsed, dict):
            raise OpenAIProviderError(
                "OpenAI structured output must decode to a JSON object."
            )

        return parsed

    def _extract_output_text(self, response_data: dict[str, Any]) -> str | None:
        output_text = response_data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        for output_item in response_data.get("output", []):
            if not isinstance(output_item, dict):
                continue
            for content_item in output_item.get("content", []):
                if not isinstance(content_item, dict):
                    continue
                text_value = content_item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    return text_value
                if isinstance(text_value, dict):
                    nested = text_value.get("value")
                    if isinstance(nested, str) and nested.strip():
                        return nested
                if content_item.get("type") == "refusal":
                    refusal = content_item.get("refusal")
                    if isinstance(refusal, str) and refusal.strip():
                        raise OpenAIProviderError(f"OpenAI refused the request: {refusal}")

        return None


__all__ = ["OpenAIProvider", "OpenAIProviderError"]
