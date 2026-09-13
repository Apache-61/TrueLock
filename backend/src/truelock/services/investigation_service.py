"""Investigation service: orchestrates detection and bounded agent execution."""
from __future__ import annotations

from typing import Any

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.investigator import ForensicInvestigator
from truelock.agent.tools import ToolRegistry
from truelock.database.repositories.memory import InMemoryRepositories
from truelock.detection.detectors import DetectionEngine
from truelock.domain.models.investigation import Case, Evidence, InvestigationStep, Lead, LeadStatus
from truelock.seeder.demo_scenario import load_demo_scenario


class InvestigationService:
    """Manages forensic investigation lifecycle from detector signals to final case."""

    def __init__(self, repo: InMemoryRepositories | None = None, gemini_client: GeminiClient | None = None) -> None:
        self.repo = repo if repo is not None else load_demo_scenario()
        self.gemini = gemini_client or GeminiClient()
        self.detector = DetectionEngine(
            entities=self.repo.entities,
            providers=self.repo.providers,
            accounts=self.repo.accounts,
            transactions=self.repo.transactions,
            invoices=self.repo.invoices,
            payments=self.repo.payments,
        )
        self.tools = ToolRegistry(
            entities=self.repo.entities,
            providers=self.repo.providers,
            accounts=self.repo.accounts,
            transactions=self.repo.transactions,
            invoices=self.repo.invoices,
            payments=self.repo.payments,
        )
        self.investigator = ForensicInvestigator(self.tools, self.gemini)

        # In-memory persistence for demo session
        self._leads: dict[str, Lead] = {}
        self._cases: dict[str, Case] = {}
        self._steps: dict[str, list[InvestigationStep]] = {}
        self._evidence: dict[str, list[Evidence]] = {}

        # Populate initial leads
        self.refresh_leads()

    def refresh_leads(self) -> list[Lead]:
        leads = self.detector.run_all()
        for lead in leads:
            self._leads[lead.lead_id] = lead
        return list(self._leads.values())

    def list_leads(self) -> list[Lead]:
        if not self._leads:
            self.refresh_leads()
        return list(self._leads.values())

    def get_lead(self, lead_id: str) -> Lead | None:
        return self._leads.get(lead_id)

    def start_investigation(self, lead_id: str) -> dict[str, Any]:
        """Execute bounded investigation on a lead."""
        lead = self.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        case, steps, evidence = self.investigator.investigate(lead)

        # Update lead status
        lead_dict = lead.to_dict()
        lead_dict["status"] = LeadStatus.FOLLOWED.value
        self._leads[lead_id] = Lead.parse(lead_dict)

        self._cases[case.case_id] = case
        self._steps[case.case_id] = steps
        self._evidence[case.case_id] = evidence

        return {
            "case": case.to_dict(),
            "steps": [s.to_dict() for s in steps],
            "evidence": [e.to_dict() for e in evidence],
        }

    def get_investigation_details(self, case_id: str) -> dict[str, Any] | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        return {
            "case": case.to_dict(),
            "steps": [s.to_dict() for s in self._steps.get(case_id, [])],
            "evidence": [e.to_dict() for e in self._evidence.get(case_id, [])],
        }
