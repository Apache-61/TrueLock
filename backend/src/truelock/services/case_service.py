"""Case service: handles case retrieval and judge Q&A over substantiated findings."""
from __future__ import annotations

import json
from typing import Any

from truelock.agent.gemini_client import GeminiClient
from truelock.domain.models.investigation import Case


class CaseService:
    """Provides case file queries and evidence-grounded Q&A for demo judges."""

    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        self.gemini = gemini_client or GeminiClient()

    def answer_question(
        self,
        case: Case,
        evidence: list[dict[str, Any]],
        question: str,
    ) -> dict[str, Any]:
        """Answer an auditor or judge question, grounded strictly in the collected evidence."""
        evidence_summary = "\n".join(
            f"- [{e.get('evidence_id')}] ({e.get('type')}, {e.get('strength')}): {e.get('claim')}"
            for e in evidence
        )

        prompt = (
            f"Case Summary:\n"
            f"ID: {case.case_id}\n"
            f"Status: {case.status}\n"
            f"Hypothesis: {case.hypothesis}\n"
            f"Amount Involved: {case.amount_involved:,.2f} MXN\n"
            f"Limitations: {', '.join(case.limitations)}\n\n"
            f"Collected Evidence Records:\n{evidence_summary}\n\n"
            f"Question: {question}\n\n"
            f"Instructions:\n"
            f"Answer the question directly, citing specific evidence IDs (e.g. [EVD-...]). "
            f"If the case evidence does not contain the answer, explicitly state that the evidence is insufficient. "
            f"Never speculate or invent facts."
        )

        resp = self.gemini.generate(
            prompt=prompt,
            system_instruction="You are TrueLock's Forensic Case Assistant. You answer questions strictly grounded on audited evidence.",
        )

        return {
            "case_id": case.case_id,
            "question": question,
            "answer": resp.content or "No response generated.",
            "is_fallback": resp.is_fallback,
            "model": resp.model,
        }
