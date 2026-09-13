"""FastAPI entry point for TrueLock."""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from truelock.agent.gemini_client import GeminiClient
from truelock.agent.provider_router import ProviderRouter
from truelock.agent.usage_ledger import UsageLedger
from truelock.api.presenters import (
    present_evidence,
    present_evidence_for_qa,
    present_investigation_details,
    present_lead,
)
from truelock.database.repositories.postgres import PostgresRepositories
from truelock.domain.models.investigation import Case
from truelock.services.case_service import CaseService
from truelock.services.demo_injection_service import DemoInjectionService
from truelock.seeder.ingestion.errors import IngestError
from truelock.services.import_service import ImportService
from truelock.services.investigation_service import InvestigationService
from truelock.services.observability_service import ObservabilityService
from truelock.settings import cors_allow_origins, settings


class StartInvestigationRequest(BaseModel):
    lead_id: str


class QuestionRequest(BaseModel):
    question: str


class InjectFraudRequest(BaseModel):
    scenario_id: str | None = Field(
        default=None,
        description="hidden_pass_through | hidden_duplicate_payment",
    )


class ClearAnalysisRequest(BaseModel):
    remove_injections: bool = Field(
        default=True,
        description="Also delete cumulative inject-fraud rows before re-running detectors",
    )


def create_app(*, use_database: bool | None = None) -> FastAPI:
    """Create the FastAPI application.

    ``use_database`` overrides persistence selection for tests. When omitted,
    PostgreSQL is used only if ``settings.database_enabled`` is true.
    """
    app = FastAPI(
        title="TrueLock Forensic Auditor API",
        version="0.3.0",
        description="Forensic accounting intelligence platform with bounded Gemini investigation agent.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins(settings.frontend_origin),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    enable_database = settings.database_enabled if use_database is None else use_database
    database = (
        PostgresRepositories(settings.database_url)
        if enable_database and settings.database_url.strip()
        else None
    )
    observability = ObservabilityService(sink=database if database else None)
    usage_ledger = UsageLedger()
    provider_router = ProviderRouter(
        config_path=Path(settings.providers_config_path),
        ledger=usage_ledger,
        on_routing_event=observability.record_routing_event,
    )
    gemini_client = GeminiClient(router=provider_router, ledger=usage_ledger)
    injection_service = DemoInjectionService()
    investigation_service = InvestigationService(gemini_client=gemini_client, database=database)
    case_service = CaseService(gemini_client=gemini_client)
    active_lead_by_case: dict[str, str] = {}

    def _wrap_investigation(details: dict[str, Any] | None, *, lead_id: str | None = None) -> dict[str, Any] | None:
        if not details:
            return None
        case_id = details.get("case", {}).get("case_id")
        if lead_id and case_id:
            active_lead_by_case[case_id] = lead_id
        return present_investigation_details(
            details,
            all_leads=investigation_service.list_leads(),
            active_lead_id=lead_id or (active_lead_by_case.get(case_id) if case_id else None),
        )

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
            "version": "0.3.0",
            "demo_mode": settings.demo_mode,
            "gemini": gemini_status,
            "database": {"status": database_status},
            "routing": provider_router.status(),
            "observability": observability.metrics_snapshot(),
        }

    @app.get("/ready")
    def readiness_check() -> dict[str, str]:
        """Ready when the process can serve traffic.

        With DATABASE_URL, PostgreSQL must be healthy. Without it (memory demo),
        the process itself is considered ready.
        """
        if database:
            try:
                if not database.check_health():
                    raise HTTPException(status_code=503, detail="Database health check failed")
            except HTTPException:
                raise
            except Exception as err:
                raise HTTPException(status_code=503, detail=f"Database unavailable: {err}") from err
        return {"status": "ready", "persistence": "postgres" if database else "memory"}

    @app.get("/api/metrics")
    def ops_metrics() -> dict[str, Any]:
        return {
            "routing": provider_router.status(),
            "observability": observability.metrics_snapshot(),
            "usage": usage_ledger.snapshot(),
            "budgets": {
                "max_investigation_steps": settings.max_investigation_steps,
                "max_investigation_seconds": settings.max_investigation_seconds,
                "hard_budget_stop_usd": provider_router.hard_budget_stop_usd,
            },
        }

    @app.get("/api/leads")
    def list_leads(
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict[str, Any]]:
        leads = investigation_service.list_leads()
        page = leads[offset : offset + limit]
        return [present_lead(lead) for lead in page]

    @app.get("/api/leads/{lead_id}")
    def get_lead(lead_id: str) -> dict[str, Any]:
        lead = investigation_service.get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return present_lead(lead)

    @app.get("/api/cases")
    def list_cases(
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> list[dict[str, Any]]:
        if not database:
            items = [
                {
                    "case_id": case_id,
                    "title": case.hypothesis,
                    "status": case.status,
                }
                for case_id, case in investigation_service._cases.items()
            ]
            return items[offset : offset + limit]
        return database.list_case_records()[offset : offset + limit]

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str) -> dict[str, Any]:
        details = investigation_service.get_investigation_details(case_id)
        wrapped = _wrap_investigation(details)
        if not wrapped:
            raise HTTPException(status_code=404, detail="Case not found")
        return wrapped["case"]

    @app.post("/api/investigations/start")
    def start_investigation(req: StartInvestigationRequest) -> dict[str, Any]:
        try:
            observability.emit(
                case_id=f"PENDING-{req.lead_id}",
                message=f"Opening investigation for lead {req.lead_id}",
                event_type="investigation_start",
            )
            raw = investigation_service.start_investigation(req.lead_id)
            presented = _wrap_investigation(raw, lead_id=req.lead_id)
            assert presented is not None
            case_id = presented["case"]["case_id"]
            observability.clear(f"PENDING-{req.lead_id}")
            observability.emit(
                case_id=case_id,
                message=f"Investigation completed with status {presented['case']['status']}",
                event_type="investigation_complete",
            )
            observability.emit_investigation_steps(case_id, presented["steps"])
            return presented
        except ValueError as err:
            raise HTTPException(status_code=404, detail=str(err))

    @app.get("/api/investigations/{case_id}")
    def get_investigation(case_id: str) -> dict[str, Any]:
        details = _wrap_investigation(investigation_service.get_investigation_details(case_id))
        if not details:
            raise HTTPException(status_code=404, detail="Investigation case not found")
        return details

    @app.get("/api/graph/{case_id}")
    def get_money_trail(case_id: str) -> dict[str, Any]:
        if database:
            graph = database.money_trail(case_id)
            if graph:
                return graph
        if not database:
            return _memory_money_trail(investigation_service, case_id)
        raise HTTPException(status_code=404, detail="Case not found")

    @app.get("/api/cases/{case_id}/findings")
    def get_case_findings(case_id: str) -> list[dict[str, Any]]:
        if database:
            findings = database.case_findings(case_id)
            if findings or database.investigation_details(case_id):
                return findings
            raise HTTPException(status_code=404, detail="Case not found")
        details = investigation_service.get_investigation_details(case_id)
        if not details:
            raise HTTPException(status_code=404, detail="Case not found")
        case = details["case"]
        if case.get("status") != "SUBSTANTIATED":
            return []
        return [
            {
                "finding_id": f"FINDING-{case_id}",
                "claim": case.get("hypothesis"),
                "status": "SUPPORTED",
                "supported_exposure_mxn": case.get("amount_involved"),
            }
        ]

    @app.get("/api/evidence/{evidence_id}")
    def get_evidence(evidence_id: str, case_id: str | None = Query(default=None)) -> dict[str, Any]:
        if case_id:
            details = investigation_service.get_investigation_details(case_id)
            if details:
                for item in details.get("evidence") or []:
                    if str(item.get("evidence_id")) == evidence_id:
                        return present_evidence(item)
        for case in list_cases():
            cid = case.get("case_id") or case.get("display_id")
            if not cid:
                continue
            details = investigation_service.get_investigation_details(str(cid))
            if not details:
                continue
            for item in details.get("evidence") or []:
                if str(item.get("evidence_id")) == evidence_id:
                    return present_evidence(item)
        raise HTTPException(status_code=404, detail="Evidence not found")

    @app.get("/api/events")
    def list_events(
        case_id: str = Query(..., description="Case display id"),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        return observability.list_events(case_id, offset=offset, limit=limit)

    @app.post("/api/cases/{case_id}/questions")
    def ask_case_question(case_id: str, req: QuestionRequest) -> dict[str, Any]:
        details = investigation_service.get_investigation_details(case_id)
        if not details:
            raise HTTPException(status_code=404, detail="Investigation case not found")

        presented = _wrap_investigation(details)
        assert presented is not None
        evidence = present_evidence_for_qa(presented["evidence"])
        step_ids = [str(step["step_id"]) for step in presented["steps"]]

        if database and not evidence:
            answer = (
                "The persisted record contains insufficient admissible evidence "
                "to answer this question."
            )
            database.persist_question(case_id, req.question, answer, [], step_ids)
            return {
                "case_id": case_id,
                "question": req.question,
                "answer": answer,
                "evidence_refs": [],
                "investigation_step_ids": step_ids,
                "model": "deterministic-persistence",
            }

        case = Case.parse(presented["case"])
        if database and evidence:
            qa = case_service.answer_question(
                case, evidence, req.question, investigation_step_ids=step_ids
            )
            database.persist_question(
                case_id,
                req.question,
                qa["answer"],
                qa["evidence_refs"],
                qa.get("investigation_step_ids") or step_ids,
            )
            return qa

        return case_service.answer_question(
            case, evidence, req.question, investigation_step_ids=step_ids
        )

    def _require_import_service() -> ImportService:
        if not database:
            raise HTTPException(
                status_code=501,
                detail="File imports require DATABASE_URL (PostgreSQL-backed API)",
            )
        try:
            database.ensure_canonical_case()
            return ImportService(database)
        except ValueError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err

    async def _persist_upload(upload: UploadFile, *, suffix: str) -> Path:
        raw = await upload.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty upload")
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            handle.write(raw)
            handle.flush()
        finally:
            handle.close()
        return Path(handle.name)

    @app.post("/api/imports/cfdi")
    async def import_cfdi(file: UploadFile = File(...)) -> dict[str, Any]:
        """Auditable CFDI XML import; returns ImportReport counts and rejections."""
        service = _require_import_service()
        path = await _persist_upload(file, suffix=".xml")
        try:
            report = service.import_cfdi(path)
        except IngestError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        finally:
            path.unlink(missing_ok=True)
        observability.emit(
            case_id="IMPORT",
            message=f"CFDI import accepted={report.accepted} rejected={report.rejected}",
            event_type="import_cfdi",
        )
        investigation_service.refresh_leads()
        return report.to_dict()

    @app.post("/api/imports/bank")
    async def import_bank(file: UploadFile = File(...)) -> dict[str, Any]:
        """Auditable bank CSV import."""
        service = _require_import_service()
        path = await _persist_upload(file, suffix=".csv")
        try:
            report = service.import_bank_csv(path)
        except IngestError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        finally:
            path.unlink(missing_ok=True)
        observability.emit(
            case_id="IMPORT",
            message=f"Bank import accepted={report.accepted} rejected={report.rejected}",
            event_type="import_bank",
        )
        investigation_service.refresh_leads()
        return report.to_dict()

    @app.post("/api/imports/efos")
    async def import_efos(
        file: UploadFile = File(...),
        snapshot_date: date | None = Query(default=None),
    ) -> dict[str, Any]:
        """SAT 69-B context import — never mutates fraud finding status alone."""
        service = _require_import_service()
        path = await _persist_upload(file, suffix=".csv")
        try:
            report = service.import_efos_69b(path, snapshot_date=snapshot_date)
        except IngestError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        finally:
            path.unlink(missing_ok=True)
        observability.emit(
            case_id="IMPORT",
            message=f"EFOS import accepted={report.accepted} rejected={report.rejected}",
            event_type="import_efos",
        )
        investigation_service.refresh_leads()
        return report.to_dict()

    @app.get("/api/demo/scenarios")
    def list_injection_scenarios() -> list[dict[str, str]]:
        return injection_service.list_scenarios()

    @app.post("/demo/inject-fraud")
    def inject_fraud(req: InjectFraudRequest) -> dict[str, Any]:
        """Judge control: introduce a hidden fraud pattern into the live dataset."""
        try:
            result = injection_service.inject(
                investigation_service, scenario_id=req.scenario_id
            )
            observability.emit(
                case_id="DEMO",
                message=f"Judge injected scenario {result['scenario_id']}",
                event_type="inject_fraud",
            )
            return result
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/api/demo/clear-analysis")
    def clear_analysis(req: ClearAnalysisRequest | None = None) -> dict[str, Any]:
        """Wipe workspace to empty (no leads) until Load demo or upload."""
        body = req or ClearAnalysisRequest()
        try:
            result = injection_service.clear_analysis(
                investigation_service,
                remove_injections=body.remove_injections,
            )
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        active_lead_by_case.clear()
        observability.clear()
        observability.emit(
            case_id="DEMO",
            message=result["message"],
            event_type="clear_analysis",
        )
        return result

    @app.post("/api/demo/load-demo")
    def load_demo() -> dict[str, Any]:
        """Seed CASE-DEMO-001 and surface detector leads."""
        try:
            result = injection_service.load_demo(investigation_service)
        except (ValueError, FileNotFoundError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        active_lead_by_case.clear()
        observability.emit(
            case_id="DEMO",
            message=result["message"],
            event_type="load_demo",
        )
        return result

    @app.post("/api/scenarios/reset")
    def reset_scenario() -> dict[str, Any]:
        """Same as clear-analysis: empty workspace, no auto leads."""
        try:
            result = injection_service.clear_analysis(
                investigation_service, remove_injections=True
            )
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        active_lead_by_case.clear()
        observability.clear()
        return {
            "status": "reset",
            "message": result["message"],
            "lead_count": result.get("lead_count", 0),
        }

    return app


def _memory_money_trail(service: InvestigationService, case_id: str) -> dict[str, Any]:
    """Build a lightweight graph from in-memory transactions for offline demos."""
    details = service.get_investigation_details(case_id)
    if not details:
        raise HTTPException(status_code=404, detail="Case not found")
    repo = service.repo
    if repo is None:
        raise HTTPException(status_code=404, detail="Case not found")

    entities: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for account in repo.accounts.list():
        entity = repo.entities.get(account.entity_id)
        if entity and entity.id not in entities:
            entities[entity.id] = {
                "entity_id": entity.id,
                "canonical_name": entity.name,
                "entity_type": str(getattr(entity.entity_type, "value", entity.entity_type)).upper(),
                "rfc": entity.rfc,
            }
    for tx in repo.transactions.list():
        edges.append(
            {
                "bank_transaction_id": tx.id,
                "component_type": "DOWNSTREAM",
                "traced_amount_mxn": tx.amount,
                "origin_entity_id": repo.accounts.get(tx.from_account).entity_id if repo.accounts.get(tx.from_account) else "",
                "destination_entity_id": repo.accounts.get(tx.to_account).entity_id if repo.accounts.get(tx.to_account) else "",
                "booked_at": tx.transaction_date.isoformat(),
            }
        )
    return {"case_id": case_id, "nodes": list(entities.values()), "edges": edges}


class _LazyASGIApp:
    """Defer ``create_app()`` until the first ASGI call or attribute access."""

    def __init__(self) -> None:
        self._app: FastAPI | None = None

    def _ensure(self) -> FastAPI:
        if self._app is None:
            self._app = create_app()
        return self._app

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure(), name)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self._ensure()(scope, receive, send)


app = _LazyASGIApp()
