"""Investigation service: orchestrates detection and bounded agent execution."""
from __future__ import annotations

from typing import Any

from threading import Lock

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.investigator import ForensicInvestigator
from truelock.agent.tools import ToolRegistry
from truelock.database.repositories.memory import InMemoryRepositories
from truelock.database.repositories.postgres import PostgresRepositories
from truelock.detection.detectors import DetectionEngine
from truelock.domain.models.investigation import Case, Evidence, InvestigationStep, Lead, LeadStatus
from truelock.seeder.demo_scenario import load_demo_scenario


class InvestigationService:
    """Manages forensic investigation lifecycle from detector signals to final case."""

    def __init__(
        self,
        repo: InMemoryRepositories | None = None,
        gemini_client: GeminiClient | None = None,
        database: PostgresRepositories | None = None,
    ) -> None:
        self.database = database
        self.repo = repo if repo is not None else (None if database else load_demo_scenario())
        self.gemini = gemini_client or GeminiClient()

        data = database if database is not None else self.repo
        assert data is not None
        self.detector = DetectionEngine(
            entities=data.entities,
            providers=data.providers,
            accounts=data.accounts,
            transactions=data.transactions,
            invoices=data.invoices,
            payments=data.payments,
        )
        self.tools = ToolRegistry(
            entities=data.entities,
            providers=data.providers,
            accounts=data.accounts,
            transactions=data.transactions,
            invoices=data.invoices,
            payments=data.payments,
        )
        self.investigator = ForensicInvestigator(self.tools, self.gemini)

        self._leads: dict[str, Lead] = {}
        self._cases: dict[str, Case] = {}
        self._steps: dict[str, list[InvestigationStep]] = {}
        self._evidence: dict[str, list[Evidence]] = {}
        self._lead_locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

        if database is None:
            # Memory demos stay empty until Load demo / inject explicitly fills data.
            pass

    def _lock_for_lead(self, lead_id: str) -> Lock:
        with self._locks_guard:
            if lead_id not in self._lead_locks:
                self._lead_locks[lead_id] = Lock()
            return self._lead_locks[lead_id]

    def refresh_leads(self) -> list[Lead]:
        leads = self.detector.run_all()
        if self.database:
            return self.database.upsert_detector_leads(leads)
        for lead in leads:
            self._leads[lead.lead_id] = lead
        return list(self._leads.values())

    def list_leads(self) -> list[Lead]:
        if self.database:
            return self.database.list_lead_records()
        return list(self._leads.values())

    def get_lead(self, lead_id: str) -> Lead | None:
        if self.database:
            lead = self.database.get_lead_record(lead_id)
            if lead:
                return lead
            for item in self.refresh_leads():
                if item.lead_id == lead_id:
                    return item
            return None
        return self._leads.get(lead_id)

    def start_investigation(self, lead_id: str) -> dict[str, Any]:
        """Execute bounded investigation on a lead (serialized per lead_id)."""
        with self._lock_for_lead(lead_id):
            return self._start_investigation_unlocked(lead_id)

    def _start_investigation_unlocked(self, lead_id: str) -> dict[str, Any]:
        """Execute bounded investigation on a lead."""
        if self.database:
            fingerprint = self.database.dataset_fingerprint()
            existing = self.database.existing_investigation_for_lead(
                lead_id, dataset_fingerprint=fingerprint
            )
            if existing:
                return existing

            lead = self.get_lead(lead_id)
            if not lead:
                raise ValueError(f"Lead {lead_id} not found")

            case, steps, evidence = self.investigator.investigate(lead)
            idempotency_key = f"{fingerprint}:{lead.lead_id}"
            return self.database.persist_investigation_result(
                lead=lead,
                case=case,
                steps=steps,
                evidence=evidence,
                idempotency_key=idempotency_key,
                dataset_fingerprint=fingerprint,
            )

        lead = self.get_lead(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        case, steps, evidence = self.investigator.investigate(lead)

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
        if self.database:
            return self.database.investigation_details(case_id)
        case = self._cases.get(case_id)
        if not case:
            return None
        return {
            "case": case.to_dict(),
            "steps": [s.to_dict() for s in self._steps.get(case_id, [])],
            "evidence": [e.to_dict() for e in self._evidence.get(case_id, [])],
        }
