"""TrueLock detection package."""
from __future__ import annotations

from .detectors import DetectionEngine
from .signals import DetectorSignal

__all__ = ["DetectionEngine", "DetectorSignal"]
