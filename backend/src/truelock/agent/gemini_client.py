"""Google Gemini client for server-side bounded forensic investigation.

Wraps the Gemini REST API for typed function calling and narrative generation.
Routes across authorized projects from ``config/agent-providers.json`` with
session budget enforcement and auditable ROUTING_EVENT failover.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from truelock.agent.provider_router import ProviderRouter
from truelock.agent.usage_ledger import UsageLedger
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
    provider_id: str | None = None
    routing_reason: str | None = None


class GeminiClient:
    """Bounded, authenticated client for the official Google Gemini API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        router: ProviderRouter | None = None,
        ledger: UsageLedger | None = None,
    ) -> None:
        self._explicit_api_key = api_key
        self.model = model or settings.gemini_model or "gemini-2.5-flash"
        self.ledger = ledger or UsageLedger()
        self.router = router or ProviderRouter(ledger=self.ledger)
        if api_key is not None:
            self.api_key = api_key
        else:
            selected = self.router.select_provider()
            self.api_key = (
                selected.resolve_api_key() if selected else settings.gemini_api_key
            )
    @property
    def is_configured(self) -> bool:
        if self._explicit_api_key is not None:
            return bool(self._explicit_api_key.strip())
        return bool(self.router.configured_providers()) or bool(
            settings.gemini_api_key and settings.gemini_api_key.strip()
        )

    def check_health(self) -> dict[str, Any]:
        """Verify API key and model connectivity."""
        routing = self.router.status()
        if not self.is_configured:
            return {
                "status": "unconfigured",
                "model": self.model,
                "message": "No Gemini API key configured. Outage fallback mode active.",
                "routing": routing,
            }

        provider = None
        if self._explicit_api_key is None:
            provider = self.router.select_provider()
            api_key = provider.resolve_api_key() if provider else ""
        else:
            api_key = self._explicit_api_key

        if not api_key:
            return {
                "status": "unconfigured",
                "model": self.model,
                "message": "Provider pool exhausted or unconfigured.",
                "routing": routing,
            }

        url = f"{GEMINI_API_BASE}/{self.model}?key={api_key}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "connected",
                    "model": self.model,
                    "display_name": data.get("displayName", self.model),
                    "provider_id": provider.id if provider else "explicit",
                    "routing": routing,
                }
            return {
                "status": "error",
                "model": self.model,
                "http_status": resp.status_code,
                "error": resp.text[:200],
                "routing": routing,
            }
        except Exception as exc:
            return {
                "status": "error",
                "model": self.model,
                "error": str(exc),
                "routing": routing,
            }

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> GeminiResponse:
        """Call Gemini generateContent with optional function declarations."""
        if self.router.budget_exhausted() and self._explicit_api_key is None:
            return self._offline_fallback(
                prompt,
                tools,
                error_msg="hard_budget_stop",
                routing_reason="hard_budget_stop",
            )

        if self._explicit_api_key is not None:
            if not self._explicit_api_key.strip():
                return self._offline_fallback(prompt, tools, error_msg="explicit empty key")
            return self._generate_with_key(
                api_key=self._explicit_api_key,
                provider_id="explicit",
                prompt=prompt,
                system_instruction=system_instruction,
                tools=tools,
            )

        attempts = 0
        last_error = None
        while attempts < max(1, len(self.router.configured_providers()) + 1):
            attempts += 1
            provider = self.router.select_provider()
            if provider is None:
                break
            api_key = provider.resolve_api_key()
            result = self._generate_with_key(
                api_key=api_key,
                provider_id=provider.id,
                prompt=prompt,
                system_instruction=system_instruction,
                tools=tools,
                record_usage=True,
                provider=provider,
            )
            if not result.is_fallback:
                return result
            # Failover on HTTP/provider errors flagged via routing_reason
            if result.routing_reason in {"http_429", "http_5xx", "transport_error"}:
                last_error = result.routing_reason
                self.router.mark_failure(provider.id, reason=result.routing_reason)
                continue
            return result

        return self._offline_fallback(
            prompt,
            tools,
            error_msg=last_error or "no_healthy_authorized_provider",
            routing_reason=last_error or "no_healthy_authorized_provider",
        )

    def _generate_with_key(
        self,
        *,
        api_key: str,
        provider_id: str,
        prompt: str,
        system_instruction: str | None,
        tools: list[dict[str, Any]] | None,
        record_usage: bool = False,
        provider: Any = None,
    ) -> GeminiResponse:
        url = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={api_key}"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if resp.status_code == 429:
                if record_usage and provider is not None:
                    self.router.record_success(
                        provider, model=self.model, status="error", error="http_429", estimated_cost=0.0
                    )
                return GeminiResponse(
                    is_fallback=True,
                    content=resp.text[:200],
                    model=self.model,
                    provider_id=provider_id,
                    routing_reason="http_429",
                )
            if resp.status_code >= 500:
                if record_usage and provider is not None:
                    self.router.record_success(
                        provider, model=self.model, status="error", error=f"http_{resp.status_code}", estimated_cost=0.0
                    )
                return GeminiResponse(
                    is_fallback=True,
                    content=resp.text[:200],
                    model=self.model,
                    provider_id=provider_id,
                    routing_reason="http_5xx",
                )
            if resp.status_code != 200:
                logger.error("Gemini API error %d: %s", resp.status_code, resp.text)
                if record_usage and provider is not None:
                    self.router.record_success(
                        provider,
                        model=self.model,
                        status="error",
                        error=f"http_{resp.status_code}",
                        estimated_cost=0.0,
                    )
                return self._offline_fallback(
                    prompt,
                    tools,
                    error_msg=resp.text,
                    provider_id=provider_id,
                    routing_reason=f"http_{resp.status_code}",
                )

            if record_usage and provider is not None:
                self.router.record_success(provider, model=self.model, status="ok")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return GeminiResponse(
                    is_fallback=True,
                    content="No candidate returned.",
                    provider_id=provider_id,
                )

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
                        provider_id=provider_id,
                    )
                if "text" in part:
                    return GeminiResponse(
                        content=part["text"],
                        finish_reason=finish_reason,
                        model=self.model,
                        is_fallback=False,
                        provider_id=provider_id,
                    )
            return GeminiResponse(
                is_fallback=False, content="", model=self.model, provider_id=provider_id
            )
        except Exception as exc:
            logger.exception("Failed calling Gemini API: %s", exc)
            if record_usage and provider is not None:
                self.router.record_success(
                    provider, model=self.model, status="error", error=str(exc), estimated_cost=0.0
                )
            return GeminiResponse(
                is_fallback=True,
                content=str(exc),
                model=self.model,
                provider_id=provider_id,
                routing_reason="transport_error",
            )

    def _offline_fallback(
        self,
        prompt: str,
        tools: list[dict[str, Any]] | None = None,
        error_msg: str | None = None,
        *,
        provider_id: str | None = None,
        routing_reason: str | None = None,
    ) -> GeminiResponse:
        """Deterministic fallback when Gemini API is unavailable or unconfigured."""
        if tools:
            return GeminiResponse(
                content=(
                    "[Offline Fallback] Investigation deferred to deterministic "
                    f"tool plan. {error_msg or ''}"
                ).strip(),
                is_fallback=True,
                model="fallback-deterministic",
                function_call=None,
                provider_id=provider_id,
                routing_reason=routing_reason or "offline_fallback",
            )

        answer = (
            "[Offline Fallback] Unable to reach the model. Based only on the "
            "case and evidence provided in the prompt, re-check the cited "
            "evidence IDs in the case file. If those records do not answer the "
            "question, the evidence is insufficient."
        )
        if error_msg:
            answer = f"{answer} ({error_msg})"
        return GeminiResponse(
            content=answer,
            is_fallback=True,
            model="fallback-deterministic",
            function_call=None,
            provider_id=provider_id,
            routing_reason=routing_reason or "offline_fallback",
        )
