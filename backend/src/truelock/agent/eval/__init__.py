"""Load corpus packs and promotion thresholds; run offline agent eval."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from truelock.agent.eval.metrics import RunMetrics, score_investigation
from truelock.agent.gemini_client import GeminiClient
from truelock.agent.policy import load_policy
from truelock.detection.detectors import DetectionEngine
from truelock.domain.models.investigation import Case
from truelock.seeder.detector_scenarios import (
    scenario_cycle_dedup,
    scenario_efos_negative_no_accusation,
    scenario_pass_through_temporal,
    scenario_shell_network,
    scenario_supplier_concentration,
    scenario_unusual_timing,
)
from truelock.services.case_service import CaseService
from truelock.services.demo_injection_service import DemoInjectionService
from truelock.services.investigation_service import InvestigationService

ROOT = Path(__file__).resolve().parents[5]
CORPUS_ROOT = ROOT / "data" / "eval_corpus"
THRESHOLDS_PATH = Path(__file__).resolve().parent / "thresholds.json"

_DATASET_FACTORIES = {
    "cycle_dedup": scenario_cycle_dedup,
    "pass_through_temporal_positive": lambda: scenario_pass_through_temporal(positive=True),
    "pass_through_temporal_negative": lambda: scenario_pass_through_temporal(positive=False),
    "unusual_timing_positive": lambda: scenario_unusual_timing(positive=True),
    "unusual_timing_negative": lambda: scenario_unusual_timing(positive=False),
    "efos_negative_no_accusation": scenario_efos_negative_no_accusation,
    "supplier_concentration_positive": lambda: scenario_supplier_concentration(positive=True),
    "shell_network_positive": lambda: scenario_shell_network(positive=True),
}


def load_thresholds() -> dict[str, Any]:
    return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))


def list_corpus_packs(split: str = "eval") -> list[Path]:
    folder = CORPUS_ROOT / split
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"))


def load_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _known_sources(service: InvestigationService) -> set[str]:
    known: set[str] = set()
    if service.repo is None:
        return known
    for tx in service.repo.transactions.list():
        known.add(tx.id)
    for payment in service.repo.payments.list():
        known.add(payment.id)
    for inv in service.repo.invoices.list():
        known.add(inv.uuid)
    for ent in service.repo.entities.list():
        known.add(ent.id)
        if ent.rfc:
            known.add(ent.rfc)
    for prov in service.repo.providers.list():
        known.add(prov.rfc)
    return known


def _service_from_dataset(dataset_key: str, gemini: GeminiClient) -> InvestigationService:
    factory = _DATASET_FACTORIES.get(dataset_key)
    if factory is None:
        raise KeyError(f"Unknown eval dataset factory: {dataset_key}")
    repo = factory()
    service = InvestigationService(repo=repo, gemini_client=gemini)
    engine = DetectionEngine(
        entities=repo.entities,
        providers=repo.providers,
        accounts=repo.accounts,
        transactions=repo.transactions,
        invoices=repo.invoices,
        payments=repo.payments,
    )
    service._leads = {lead.lead_id: lead for lead in engine.run_all()}
    return service


def _service_for_pack(pack: dict[str, Any], gemini: GeminiClient) -> InvestigationService:
    lead_spec = pack.get("input_lead") or {}
    scenario_id = pack.get("scenario_id")
    dataset_key = pack.get("dataset") or scenario_id
    if dataset_key in _DATASET_FACTORIES:
        return _service_from_dataset(str(dataset_key), gemini)
    if lead_spec.get("detector_id") == "69B_CORRELATION":
        return _service_from_dataset("efos_negative_no_accusation", gemini)
    service = InvestigationService(gemini_client=gemini)
    if scenario_id in {"hidden_pass_through", "hidden_duplicate_payment"}:
        DemoInjectionService().inject(service, scenario_id=str(scenario_id))
    return service


def run_pack(
    pack: dict[str, Any],
    *,
    split: str,
    service: InvestigationService | None = None,
) -> RunMetrics:
    """Execute one corpus pack against the offline investigator and score it."""
    thresholds = load_thresholds()
    policy = load_policy()
    gemini = GeminiClient(api_key="")
    service = service or _service_for_pack(pack, gemini)

    lead_spec = pack.get("input_lead") or {}
    lead_id = lead_spec.get("lead_id")
    leads = service.list_leads()
    lead = None
    if lead_id:
        lead = next((item for item in leads if item.lead_id == lead_id), None)
    if lead is None and lead_spec.get("entity_id"):
        lead = next(
            (
                item
                for item in leads
                if item.entity_id == lead_spec["entity_id"]
                and (
                    not lead_spec.get("detector_id")
                    or item.detector_id == lead_spec["detector_id"]
                )
            ),
            None,
        )
    if lead is None and lead_spec.get("detector_id"):
        lead = next(
            (item for item in leads if item.detector_id == lead_spec["detector_id"]),
            None,
        )

    if lead is None:
        return RunMetrics(
            corpus_id=str(pack.get("corpus_id", "unknown")),
            split=split,
            policy_version=policy.version,
            model="offline-fallback",
            eval_seed=str(thresholds.get("eval_seed", "")),
            valid_args_rate=0.0,
            repeated_tool_calls=0,
            source_coverage=0.0,
            terminal_decision="ESCALATE",
            terminal_ok=False,
            case_status="MISSING",
            exposure_ok=False,
            invented_sources=0,
            step_count=0,
            failures=["lead_not_found"],
            gates_passed=False,
        )

    result = service.start_investigation(lead.lead_id)
    case = result["case"]
    steps = result["steps"]
    evidence = result["evidence"]
    case_dict = case if isinstance(case, dict) else case.to_dict()
    step_dicts = [s if isinstance(s, dict) else s.to_dict() for s in steps]
    evidence_dicts = [e if isinstance(e, dict) else e.to_dict() for e in evidence]

    qa_payload = None
    questions = pack.get("audit_questions") or []
    must_ref = any(q.get("must_include_evidence_refs") for q in questions)
    if must_ref and case_dict.get("case_id"):
        case_obj = Case.parse(case_dict)
        ask = next(q["question"] for q in questions if q.get("must_include_evidence_refs"))
        qa_payload = CaseService(gemini_client=gemini).answer_question(
            case=case_obj,
            evidence=evidence_dicts,
            question=ask,
            investigation_step_ids=[s.get("step_id") for s in step_dicts if s.get("step_id")],
        )

    return score_investigation(
        corpus=pack,
        split=split,
        case=case_dict,
        steps=step_dicts,
        evidence=evidence_dicts,
        known_source_ids=_known_sources(service),
        policy_version=policy.version,
        model="offline-fallback",
        eval_seed=str(thresholds.get("eval_seed", "")),
        thresholds=thresholds,
        qa_payload=qa_payload,
    )


def evaluate_split(split: str = "eval") -> list[RunMetrics]:
    return [run_pack(load_pack(path), split=split) for path in list_corpus_packs(split)]


def promotion_gate(split: str = "eval") -> tuple[bool, list[RunMetrics]]:
    """Return (passed, metrics). Fail-closed if any pack fails its gates."""
    results = evaluate_split(split)
    return (bool(results) and all(item.gates_passed for item in results), results)
