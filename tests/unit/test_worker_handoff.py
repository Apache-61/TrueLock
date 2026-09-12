"""Handoff and AI result parsing (handoff.py, adapters/base.py).

Covers the two contracts the rest of the system reads: the structured
result an AI must return, and the `task-result.json` + history entry the
next worker picks up instead of a conversation transcript.
"""
from __future__ import annotations

import json

import pytest

from orchestrator.workers.adapters.base import (
    AdapterError,
    AIResult,
    extract_result,
    result_from_dict,
)
from orchestrator.workers.handoff import Handoff, new_run_id, requires_adr

VALID = {
    "task_id": "TASK-007",
    "status": "DONE",
    "summary": "Implemented the worker adapters.",
    "changed_files": ["orchestrator/workers/runner.py"],
    "tests": {"passed": 12, "failed": 0, "skipped": 1, "details": "pytest tests/unit"},
    "new_dependencies": [],
    "known_issues": ["The Gemini adapter is deferred."],
    "documentation_changes": ["orchestrator/README.md"],
    "next_recommended_tasks": ["TASK-001"],
    "requires_human_review": False,
}


class TestExtractResult:
    def test_bare_json_object(self):
        result = extract_result(json.dumps(VALID))
        assert result.status == "DONE"
        assert result.tests.passed == 12
        assert result.changed_files == ["orchestrator/workers/runner.py"]

    def test_fenced_json_after_prose(self):
        text = f"I implemented it.\n\n```json\n{json.dumps(VALID)}\n```"
        assert extract_result(text).status == "DONE"

    def test_the_last_object_wins_when_the_model_corrects_itself(self):
        first = dict(VALID, status="PARTIAL", summary="first attempt")
        text = f"```json\n{json.dumps(first)}\n```\nActually:\n```json\n{json.dumps(VALID)}\n```"
        assert extract_result(text).summary == "Implemented the worker adapters."

    def test_unfenced_object_embedded_in_prose(self):
        text = f"Here is the result: {json.dumps(VALID)} -- done."
        assert extract_result(text).status == "DONE"

    def test_braces_inside_strings_do_not_break_extraction(self):
        payload = dict(VALID, summary="used a dict literal {\"a\": 1} in the code")
        assert extract_result(f"```json\n{json.dumps(payload)}\n```").status == "DONE"

    def test_empty_output_is_an_error_not_a_success(self):
        with pytest.raises(AdapterError):
            extract_result("")

    def test_unparseable_output_is_an_error_not_a_success(self):
        """A model that cannot answer in contract has not done the task."""
        with pytest.raises(AdapterError) as caught:
            extract_result("I finished the task successfully!")
        assert "parseable result" in str(caught.value)

    def test_error_quotes_the_raw_output_for_diagnosis(self):
        with pytest.raises(AdapterError) as caught:
            extract_result("something went sideways")
        assert "something went sideways" in str(caught.value)


class TestResultCoercion:
    def test_unknown_status_becomes_failed_not_done(self):
        """Defaulting an unrecognised status to success would let a
        confused model mark its own homework."""
        assert result_from_dict({"status": "mostly fine"}).status == "FAILED"

    @pytest.mark.parametrize("alias", ["SUCCESS", "ok", "complete", "COMPLETED"])
    def test_common_success_synonyms_are_accepted(self, alias):
        assert result_from_dict({"status": alias}).status == "DONE"

    def test_a_string_where_a_list_belongs_is_coerced(self):
        result = result_from_dict({"status": "DONE", "changed_files": "a.py"})
        assert result.changed_files == ["a.py"]

    def test_missing_fields_default_safely(self):
        result = result_from_dict({"status": "DONE"}, task_id="TASK-001")
        assert result.task_id == "TASK-001"
        assert result.changed_files == []
        assert result.tests.passed == 0

    def test_both_spellings_of_next_tasks_are_accepted(self):
        """orchestrator/README.md says `next_recommended_tasks`; some task
        briefs say `recommended_next_tasks`. Neither reader should break."""
        assert result_from_dict(
            {"status": "DONE", "recommended_next_tasks": ["TASK-002"]}
        ).next_recommended_tasks == ["TASK-002"]
        assert result_from_dict(
            {"status": "DONE", "next_recommended_tasks": ["TASK-002"]}
        ).next_recommended_tasks == ["TASK-002"]

    def test_serialization_emits_both_spellings(self):
        data = result_from_dict(VALID).to_dict()
        assert data["next_recommended_tasks"] == data["recommended_next_tasks"] == ["TASK-001"]

    def test_succeeded_covers_done_and_partial_only(self):
        assert result_from_dict({"status": "DONE"}).succeeded
        assert result_from_dict({"status": "PARTIAL"}).succeeded
        assert not result_from_dict({"status": "BLOCKED"}).succeeded
        assert not result_from_dict({"status": "FAILED"}).succeeded


class TestAdrEscalation:
    @pytest.mark.parametrize("path", [
        "ARCHITECTURE.md",
        "docs/contracts/api.md",
        "domain/schemas/lead.schema.json",
        "database/migrations/0002_add.sql",
        "DECISIONS.md",
    ])
    def test_architectural_surface_demands_an_adr(self, path):
        assert requires_adr([path])

    def test_ordinary_code_does_not(self):
        assert requires_adr(["orchestrator/workers/runner.py", "tests/unit/test_x.py"]) == []

    def test_leading_dot_slash_does_not_evade_the_check(self):
        assert requires_adr(["./ARCHITECTURE.md"])


class TestHandoff:
    def build(self, **kwargs) -> Handoff:
        defaults = dict(
            run_id="AI-RUN-20260912T120000Z-abc123",
            worker_id="WORKER-01",
            task_id="TASK-007",
            issue_number=7,
            branch="feature/TASK-007-worker",
            started_at="2026-09-12T12:00:00+00:00",
            finished_at="2026-09-12T12:30:00+00:00",
            goal="Build the worker",
            outcome="DONE",
            result=result_from_dict(VALID),
            validation_summary="PASSED -- 5 gate(s) passed, 0 failed, 2 skipped",
        )
        defaults.update(kwargs)
        return Handoff(**defaults)

    def test_json_carries_every_field_the_protocol_requires(self):
        data = self.build().to_dict()
        for field in ("task_id", "status", "summary", "changed_files", "tests",
                      "new_dependencies", "known_issues", "documentation_changes",
                      "next_recommended_tasks", "requires_human_review"):
            assert field in data, field

    def test_run_metadata_is_recorded(self):
        run = self.build().to_dict()["run"]
        assert run["worker_id"] == "WORKER-01"
        assert run["branch"] == "feature/TASK-007-worker"
        assert run["started_at"] and run["finished_at"]

    def test_an_adr_requirement_forces_human_review(self):
        data = self.build(adr_required=["ARCHITECTURE.md"]).to_dict()
        assert data["requires_human_review"] is True

    def test_an_experiment_forces_human_review(self):
        assert self.build(experiment_required=True).to_dict()["requires_human_review"] is True

    def test_a_missing_summary_is_reported_not_invented(self):
        handoff = self.build(result=AIResult(task_id="TASK-007", status="FAILED"))
        assert "No summary was returned" in handoff.to_dict()["summary"]

    def test_markdown_contains_every_section_the_protocol_requires(self):
        markdown = self.build().render_markdown()
        for heading in ("## Goal", "## Changes", "## Summary", "## Tests",
                        "## Known issues", "## Next recommended tasks"):
            assert heading in markdown, heading
        for field in ("worker", "task", "branch", "start", "end", "result"):
            assert f"**{field}:**" in markdown, field

    def test_markdown_embeds_the_machine_readable_handoff(self):
        markdown = self.build().render_markdown()
        start = markdown.index("```json", markdown.index("Handoff ("))
        payload = markdown[start + 7 : markdown.index("```", start + 7)]
        assert json.loads(payload)["task_id"] == "TASK-007"

    def test_adr_requirement_is_shouted_in_the_markdown(self):
        markdown = self.build(adr_required=["docs/contracts/api.md"]).render_markdown()
        assert "ADR REQUIRED" in markdown
        assert "docs/contracts/api.md" in markdown

    def test_scope_violations_appear_under_known_issues(self):
        markdown = self.build(scope_violations=["`frontend/x.tsx`: outside allowed_paths"]).render_markdown()
        assert "Scope violation" in markdown
        assert "frontend/x.tsx" in markdown

    def test_filename_follows_the_repository_convention(self):
        handoff = self.build()
        name = handoff.history_filename()
        assert name.startswith("2026-09-12-task-007-")
        assert handoff.run_id.lower() in name
        assert name.endswith(".md")

    def test_writing_creates_both_artifacts(self, tmp_path):
        paths = self.build().write(tmp_path)
        assert paths["history"].is_file()
        assert paths["task_result"].is_file()
        assert json.loads(paths["task_result"].read_text())["task_id"] == "TASK-007"

    def test_dry_run_writes_nothing(self, tmp_path):
        paths = self.build().write(tmp_path, dry_run=True)
        assert not paths["history"].exists()
        assert not paths["task_result"].exists()


class TestRunId:
    def test_run_ids_are_unique_and_sortable(self):
        ids = [new_run_id() for _ in range(50)]
        assert len(set(ids)) == 50
        assert all(run_id.startswith("AI-RUN-") for run_id in ids)
