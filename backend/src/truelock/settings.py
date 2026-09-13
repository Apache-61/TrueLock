"""Typed backend settings for TrueLock."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Server-side settings for API, database, and forensic investigator."""

    # Server & CORS
    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    frontend_origin: str = field(default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"))

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )

    # Google Gemini API
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    # Agent constraints & budgets
    max_investigation_steps: int = field(
        default_factory=lambda: int(os.getenv("MAX_INVESTIGATION_STEPS", "10"))
    )
    max_session_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MAX_SESSION_BUDGET_USD", "75.0"))
    )

    # Demo & fixture paths
    demo_mode: bool = field(
        default_factory=lambda: os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
    )

    @property
    def database_enabled(self) -> bool:
        """Only a configured server-side URL enables production persistence."""
        return bool(self.database_url.strip())


settings = Settings()
