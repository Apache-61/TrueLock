"""Unit tests for CORS origin expansion."""
from __future__ import annotations

from truelock.settings import cors_allow_origins


def test_cors_includes_www_twin_for_apex() -> None:
    origins = cors_allow_origins("https://truelockfa.tech")
    assert "https://truelockfa.tech" in origins
    assert "https://www.truelockfa.tech" in origins
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins


def test_cors_includes_apex_twin_for_www() -> None:
    origins = cors_allow_origins("https://www.truelockfa.tech")
    assert "https://www.truelockfa.tech" in origins
    assert "https://truelockfa.tech" in origins


def test_cors_strips_trailing_slash() -> None:
    origins = cors_allow_origins("https://truelockfa.tech/")
    assert "https://truelockfa.tech" in origins
    assert "https://truelockfa.tech/" not in origins
