"""FastAPI entry point for TrueLock."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from truelock.agent.gemini_client import GeminiClient
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
    investigation_service = InvestigationService(gemini_client=gemini_client)
    case_service = CaseService(gemini_client=gemini_client)

    @app.get("/health")
    def health_check() -> dict[str, Any]:
        gemini_status = gemini_client.check_health()
        return {
            "status": "ok",
            "version": "0.1.0",
            "demo_mode": settings.demo_mode,
            "gemini": gemini_status,
        }

    @app.get("/api/leads")
    def list_leads() -> list[dict[str, Any]]:
        return [lead.to_dict() for lead in investigation_service.list_leads()]

    @app.get("/api/leads/{lead_id}")
    def get_lead(lead_id: str) -> dict[str, Any]:
        lead = investigation_service.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead.to_dict()

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

    @app.post("/api/cases/{case_id}/questions")
    def ask_case_question(case_id: str, req: QuestionRequest) -> dict[str, Any]:
        details = investigation_service.get_investigation_details(case_id)
        if not details:
            raise HTTPException(status_code=404, detail="Investigation case not found")

        case = Case.parse(details["case"])
        evidence = details["evidence"]
        return case_service.answer_question(case, evidence, req.question)

    @app.post("/api/scenarios/reset")
    def reset_scenario() -> dict[str, str]:
        investigation_service.refresh_leads()
        return {"status": "reset", "message": "Demo scenario reloaded."}

    return app


app = create_app()
