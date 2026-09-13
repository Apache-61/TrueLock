"""Google Gemini client for server-side bounded forensic investigation.

Wraps the Gemini REST API for typed function calling and narrative generation.
Never receives raw SQL access, system shell access, or secret keys from the frontend.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import requests

from truelock.settings import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class GeminiResponse:
    content: str | None = None
    function_call: dict[str, Any] | None = None
    finish_reason: str | None = None
    model: str = ""
    is_fallback: bool = False


class GeminiClient:
    """Bounded, authenticated client for the official Google Gemini API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model or "gemini-2.5-flash"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def check_health(self) -> dict[str, Any]:
        """Verify API key and model connectivity."""
        if not self.is_configured:
            return {
                "status": "unconfigured",
                "model": self.model,
                "message": "GEMINI_API_KEY is not set. Outage fallback mode active.",
            }
        url = f"{GEMINI_API_BASE}/{self.model}?key={self.api_key}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "connected",
                    "model": self.model,
                    "display_name": data.get("displayName", self.model),
                }
            return {
                "status": "error",
                "model": self.model,
                "http_status": resp.status_code,
                "error": resp.text[:200],
            }
        except Exception as exc:
            return {"status": "error", "model": self.model, "error": str(exc)}

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> GeminiResponse:
        """Call Gemini generateContent with optional function declarations."""
        if not self.is_configured:
            logger.warning("Gemini API key not configured; using offline fallback.")
            return self._offline_fallback(prompt, tools)

        url = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={self.api_key}"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error("Gemini API error %d: %s", resp.status_code, resp.text)
                return self._offline_fallback(prompt, tools, error_msg=resp.text)

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return GeminiResponse(is_fallback=True, content="No candidate returned.")

            candidate = candidates[0]
            finish_reason = candidate.get("finishReason")
            parts = candidate.get("content", {}).get("parts", [])

            for part in parts:
                if "functionCall" in part:
                    fc = part["functionCall"]
                    return GeminiResponse(
                        function_call={"name": fc.get("name"), "args": fc.get("args", {})},
                        finish_reason=finish_reason,
                        model=self.model,
                        is_fallback=False,
                    )
                if "text" in part:
                    return GeminiResponse(
                        content=part["text"],
                        finish_reason=finish_reason,
                        model=self.model,
                        is_fallback=False,
                    )

            return GeminiResponse(is_fallback=False, content="", model=self.model)

        except Exception as exc:
            logger.exception("Failed calling Gemini API: %s", exc)
            return self._offline_fallback(prompt, tools, error_msg=str(exc))

    def _offline_fallback(
        self,
        prompt: str,
        tools: list[dict[str, Any]] | None = None,
        error_msg: str | None = None,
    ) -> GeminiResponse:
        """Deterministic fallback when Gemini API is unavailable or unconfigured."""
        # If tools were supplied, select the appropriate next tool based on prompt context
        if tools:
            tool_names = [t["name"] for t in tools]
            if "trace_outgoing_funds" in tool_names and ("round_trip" in prompt or "rapid" in prompt or "TX-" in prompt):
                return GeminiResponse(
                    function_call={"name": "trace_outgoing_funds", "args": {"depth": 3}},
                    is_fallback=True,
                    model="fallback-deterministic",
                )
            if "inspect_counterparties" in tool_names:
                return GeminiResponse(
                    function_call={"name": "inspect_counterparties", "args": {}},
                    is_fallback=True,
                    model="fallback-deterministic",
                )
            if tool_names:
                return GeminiResponse(
                    function_call={"name": tool_names[0], "args": {}},
                    is_fallback=True,
                    model="fallback-deterministic",
                )

        return GeminiResponse(
            content=f"[Offline Fallback] Investigation completed deterministically. {error_msg or ''}".strip(),
            is_fallback=True,
            model="fallback-deterministic",
        )
