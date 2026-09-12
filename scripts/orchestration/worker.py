#!/usr/bin/env python3
"""Entry point for the AI development worker.

    python scripts/orchestration/worker.py start --once

Put `scripts/orchestration/` on PATH and the same command becomes:

    worker start --once

This file stays a thin launcher: it makes the repository importable and
hands over to `orchestrator.workers.cli`. All behaviour lives in the
package, so it is unit-testable without spawning a process.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.workers.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
