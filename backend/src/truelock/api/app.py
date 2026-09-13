"""FastAPI entry point for TrueLock."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from truelock.agent.gemini_client import GeminiClient
from truelock.database.repositories.postgres import PostgresRepositories
from truelock.domain.models.investigation import Case
from truelock.services.case_service import CaseService
from truelock.services.investigation_service import InvestigationService
from truelock.settings import settings


class StartInvestigationRequest(BaseModel):
    lead_id: str


class QuestionRequest(BaseModel):
    question: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrueLock Forensic Auditor API",
        version="0.1.0",
        description="Forensic accounting intelligence platform with bounded Gemini investigation agent.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    gemini_client = GeminiClient()
    database = PostgresRepositories(settings.database_url) if settings.database_enabled else None
    investigation_service = InvestigationService(gemini_client=gemini_client, database=database)
    case_service = CaseService(gemini_client=gemini_client)

    @app.get("/health")
    def health_check() -> dict[str, Any]:
        gemini_status = gemini_client.check_health()
        database_status = "not_configured"
        if database:
            try:
                database_status = "ok" if database.check_health() else "unavailable"
            except Exception:
                database_status = "unavailable"
        return {
            "status": "ok",
            "version": "0.1.0",
            "demo_mode": settings.demo_mode,
            "gemini": gemini_status,
            "database": {"status": database_status},
        }

    @app.get("/ready")
    def readiness_check() -> dict[str, str]:
        if not database:
            raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
        try:
            if not database.check_health():
                raise HTTPException(status_code=503, detail="Database health check failed")
        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(status_code=503, detail=f"Database unavailable: {err}") from err
        return {"status": "ready"}

    @app.get("/api/leads")
    def list_leads() -> list[dict[str, Any]]:
        return [
            lead if isinstance(lead, dict) else lead.to_dict()
            for lead in investigation_service.list_leads()
        ]

    @app.get("/api/leads/{lead_id}")
    def get_lead(lead_id: str) -> dict[str, Any]:
        lead = investigation_service.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead if isinstance(lead, dict) else lead.to_dict()

    @app.get("/api/cases")
    def list_cases() -> list[dict[str, Any]]:
        if not database:
            return []
        return database.list_case_records()

    @app.post("/api/investigations/start")
    def start_investigation(req: StartInvestigationRequest) -> dict[str, Any]:
        try:
            return investigation_service.start_investigation(req.lead_id)
        except ValueError as err:
            raise HTTPException(status_code=404, detail=str(err))

    @app.get("/api/investigations/{case_id}")
    def get_investigation(case_id: str) -> dict[str, Any]:
        details = investigation_service.get_investigation_details(case_id)
        if not details:
            raise HTTPException(status_code=404, detail="Investigation case not found")
        return details

    @app.get("/api/graph/{case_id}")
    def get_money_trail(case_id: str) -> dict[str, Any]:
        if not database:
            raise HTTPException(status_code=503, detail="Financial graph requires DATABASE_URL")
        graph = database.money_trail(case_id)
        if not graph:
            raise HTTPException(status_code=404, detail="Case not found")
        return graph

    @app.get("/api/cases/{case_id}/findings")
    def get_case_findings(case_id: str) -> list[dict[str, Any]]:
        if not database:
            raise HTTPException(status_code=503, detail="Findings require DATABASE_URL")
        findings = database.case_findings(case_id)
        if not findings and not database.investigation_details(case_id):
            raise HTTPException(status_code=404, detail="Case not found")
        return findings

    @app.post("/api/cases/{case_id}/questions")
    def ask_case_question(case_id: str, req: QuestionRequest) -> dict[str, Any]:
        details = investigation_service.get_investigation_details(case_id)
        if not details:
            raise HTTPException(status_code=404, detail="Investigation case not found")

        if database:
            evidence_ids = [item["evidence_id"] for item in details["evidence"]]
            step_ids = [item["step_id"] for item in details["steps"]]
            finding = details.get("finding")
            answer = (
                f"Persisted evidence supports finding {finding['display_id']}: {finding['claim']}"
                if finding
                else "The persisted record contains insufficient evidence for a supported finding."
            )
            database.persist_question(case_id, req.question, answer, evidence_ids, step_ids)
            return {
                "case_id": details["case"]["case_id"],
                "question": req.question,
                "answer": answer,
                "evidence_refs": evidence_ids,
                "investigation_step_ids": step_ids,
                "model": "deterministic-persistence",
            }
        case = Case.parse(details["case"])
        evidence = details["evidence"]
        return case_service.answer_question(case, evidence, req.question)

    @app.post("/api/scenarios/reset")
    def reset_scenario() -> dict[str, str]:
        investigation_service.refresh_leads()
        return {"status": "reset", "message": "Demo scenario reloaded."}

    return app


app = create_app()
