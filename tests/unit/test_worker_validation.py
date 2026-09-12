"""The validation pipeline (orchestrator/workers/validation.py).

The property under test: **"we did not check" never reads as "it
passed."** A missing tool is `skipped`; only a gate that ran and
succeeded is `passed`; a failing required gate makes the whole report
not-ok, which is what withholds a non-draft PR.
"""
from __future__ import annotations


from orchestrator.workers.validation import GateResult, ValidationReport, Validator


def report_with(*gates: GateResult) -> ValidationReport:
    report = ValidationReport()
    for gate in gates:
        report.add(gate)
    return report


class TestVerdict:
    def test_all_passing_is_ok(self):
        report = report_with(
            GateResult("unit", "passed", "pytest -q tests/unit"),
            GateResult("contract", "passed", "pytest -q tests/contract"),
        )
        assert report.ok
        assert "PASSED" in report.summary()

    def test_a_failing_required_gate_fails_the_report(self):
        report = report_with(
            GateResult("unit", "failed", "pytest -q tests/unit", "1 failed"),
        )
        assert not report.ok
        assert "FAILED" in report.summary()

    def test_a_failing_advisory_gate_does_not_fail_the_report(self):
        """Lint and formatting are nits; they must not withhold a correct
        implementation from human review."""
        report = report_with(
            GateResult("lint", "failed", "ruff check .", "E501", required=False),
            GateResult("unit", "passed", "pytest -q tests/unit"),
        )
        assert report.ok

    def test_skipped_gates_are_not_counted_as_passed(self):
        report = report_with(
            GateResult("type check", "skipped", "mypy .", "mypy is not installed"),
        )
        assert report.ok          # nothing failed ...
        assert report.passed == 0  # ... but nothing passed either
        assert report.skipped == 1
        assert "0 gate(s) passed" in report.summary()
        assert "1 skipped" in report.summary()

    def test_summary_always_discloses_skips(self):
        report = report_with(
            GateResult("unit", "passed", "pytest"),
            GateResult("integration", "skipped", "pytest tests/integration", "no tests"),
        )
        assert "1 skipped" in report.summary()

    def test_failures_are_listed_with_their_output(self):
        report = report_with(
            GateResult("unit", "failed", "pytest -q tests/unit", "assert 1 == 2"),
        )
        assert [gate.name for gate in report.failures()] == ["unit"]
        assert "assert 1 == 2" in report.render()


class TestPytestCounts:
    def test_counts_are_parsed_from_pytest_output(self):
        report = report_with(
            GateResult("unit", "passed", "pytest -q tests/unit", "28 passed in 0.12s"),
            GateResult("contract", "failed", "pytest -q tests/contract",
                       "2 failed, 5 passed, 1 skipped in 0.3s"),
        )
        assert report.pytest_counts() == (33, 2, 1)

    def test_no_pytest_output_yields_zeros(self):
        report = report_with(GateResult("lint", "passed", "ruff check .", "ok"))
        assert report.pytest_counts() == (0, 0, 0)


class TestValidatorGateSelection:
    def test_missing_tool_is_skipped_with_an_explicit_warning(self, tmp_path):
        validator = Validator(tmp_path)
        gate = validator._run("imaginary", ["definitely-not-installed-xyz", "--check"])
        assert gate.status == "skipped"
        assert "NOT the same as passing" in gate.output

    def test_gates_with_no_tests_are_skipped_not_run(self, tmp_path):
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        report = Validator(tmp_path, dry_run=True).run()
        names = {gate.name: gate for gate in report.gates}
        integration = next(g for n, g in names.items() if "integration" in n)
        assert integration.status == "skipped"
        assert "no tests under tests/integration" in integration.output

    def test_dry_run_runs_nothing(self, tmp_path):
        report = Validator(tmp_path, dry_run=True).run()
        assert report.passed == 0
        assert all(gate.status == "skipped" for gate in report.gates)

    def test_a_real_failing_test_is_reported_as_failed(self, tmp_path):
        """End-to-end through the real subprocess path: a red test must
        make the report not-ok, because that is what turns the PR into a
        draft marked FAILED."""
        unit = tmp_path / "tests" / "unit"
        unit.mkdir(parents=True)
        (unit / "test_red.py").write_text("def test_red():\n    assert False\n")
        report = Validator(tmp_path, timeout=120).run()
        unit_gate = next(gate for gate in report.gates if "unit tests" in gate.name)
        if unit_gate.status == "skipped":  # pytest not on PATH in this env
            return
        assert unit_gate.status == "failed"
        assert not report.ok

    def test_a_real_passing_test_is_reported_as_passed(self, tmp_path):
        unit = tmp_path / "tests" / "unit"
        unit.mkdir(parents=True)
        (unit / "test_green.py").write_text("def test_green():\n    assert True\n")
        report = Validator(tmp_path, timeout=120).run()
        unit_gate = next(gate for gate in report.gates if "unit tests" in gate.name)
        if unit_gate.status == "skipped":
            return
        assert unit_gate.status == "passed"
        assert report.ok


class TestVerifiedVersusOk:
    """'Nothing failed' and 'something passed' are different claims."""

    def test_all_skipped_is_ok_but_not_verified(self):
        report = report_with(
            GateResult("unit", "skipped", "pytest -q tests/unit", "pytest not installed"),
            GateResult("contract", "skipped", "pytest -q tests/contract", "no tests"),
        )
        assert report.ok
        assert not report.verified
        assert "NOT VERIFIED" in report.summary()

    def test_one_real_pass_is_verified(self):
        report = report_with(
            GateResult("unit", "passed", "pytest -q tests/unit", "3 passed"),
            GateResult("integration", "skipped", "pytest tests/integration", "no tests"),
        )
        assert report.verified
        assert report.summary().startswith("PASSED")

    def test_a_failure_is_neither_ok_nor_verified(self):
        report = report_with(GateResult("unit", "failed", "pytest", "1 failed"))
        assert not report.ok
        assert not report.verified
        assert report.summary().startswith("FAILED")

    def test_an_advisory_pass_alone_counts_as_verified_but_says_what_ran(self):
        report = report_with(
            GateResult("lint", "passed", "ruff check .", "ok", required=False),
            GateResult("unit", "skipped", "pytest", "no tests"),
        )
        assert report.verified
        assert "1 gate(s) passed" in report.summary()
