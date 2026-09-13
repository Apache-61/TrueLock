#!/usr/bin/env python3
"""Live / offline agent training loop (plan Phase 2).

Runs the train corpus with a real Gemini client when keys are configured,
otherwise falls back to the deterministic offline investigator (still useful
for corpus/harness validation). Always re-checks the blocked eval gate.

Usage:
  PYTHONPATH=backend/src python scripts/train_agent_live.py
  PYTHONPATH=backend/src python scripts/train_agent_live.py --split train
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

# Optional local .env without python-dotenv dependency.
_env_path = ROOT / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from truelock.agent.eval import evaluate_split, promotion_gate  # noqa: E402
from truelock.agent.gemini_client import GeminiClient  # noqa: E402
from truelock.settings import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="TrueLock agent training loop")
    parser.add_argument("--split", default="train", choices=["train", "eval"])
    args = parser.parse_args()

    client = GeminiClient()
    mode = "live-gemini" if client.is_configured else "offline-fallback"
    print(f"training_mode={mode} model={client.model}")

    results = evaluate_split(args.split)
    train_payload = [item.to_dict() for item in results]
    failed = [item for item in results if not item.gates_passed]
    print(
        json.dumps(
            {
                "split": args.split,
                "mode": mode,
                "passed": not failed,
                "results": train_payload,
            },
            indent=2,
        )
    )

    gate_ok, gate_results = promotion_gate("eval")
    print(
        json.dumps(
            {
                "promotion_gate": gate_ok,
                "eval_results": [item.to_dict() for item in gate_results],
            },
            indent=2,
        )
    )

    log_path = ROOT / "docs" / "agent" / "training-log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "model": client.model,
        "split": args.split,
        "train_passed": not failed,
        "promotion_gate": gate_ok,
        "failures": {
            item.corpus_id: item.failures for item in failed + [g for g in gate_results if not g.gates_passed]
        },
        "gemini_configured": client.is_configured,
        "providers_config": settings.providers_config_path,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    print(f"appended_log={log_path}")

    if not gate_ok:
        print("PROMOTION GATE FAILED — do not promote policy/few-shot changes", file=sys.stderr)
        return 1
    if failed and args.split == "train":
        print(
            "TRAIN PACKS HAVE FAILURES — iterate policy/few-shot, then re-run",
            file=sys.stderr,
        )
        return 2
    print("TRAINING LOOP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
