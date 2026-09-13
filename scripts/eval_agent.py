#!/usr/bin/env python3
"""Run the blocked eval corpus promotion gate (Fase 6)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from truelock.agent.eval import promotion_gate


def main() -> int:
    passed, results = promotion_gate("eval")
    payload = [item.to_dict() for item in results]
    print(json.dumps({"passed": passed, "results": payload}, indent=2))
    if not passed:
        print("PROMOTION GATE FAILED", file=sys.stderr)
        for item in results:
            if not item.gates_passed:
                print(f"- {item.corpus_id}: {item.failures}", file=sys.stderr)
        return 1
    print("PROMOTION GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
