"""Integration coverage for the PostgreSQL migrations and demo seed."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from truelock.database.repositories.postgres import PostgresRepositories
from truelock.services.import_service import ImportService
from truelock.services.investigation_service import InvestigationService


ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "data" / "fixtures"


def _bash_executable() -> str:
    """Prefer Git Bash on Windows; WSL bash breaks path/env for repo scripts."""
    candidates = [
        os.environ.get("TRUELOCK_BASH"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "bash"


def _bash_env(database_url: str) -> dict[str, str]:
    """Env for Git Bash on Windows — MSYS path conversion can strip URI env vars."""
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "MSYS_NO_PATHCONV": "1",
        "MSYS2_ARG_CONV_EXCL": "*",
    }
    # Also export discrete libpq vars so migrate/seed work even if the URI is mangled.
    prefix = "postgresql://"
    if database_url.startswith(prefix) or database_url.startswith("postgres://"):
        rest = database_url.split("://", 1)[1]
        userinfo, _, hostinfo = rest.partition("@")
        user, _, password = userinfo.partition(":")
        hostport, _, dbname = hostinfo.partition("/")
        host, _, port = hostport.partition(":")
        env.update(
            {
                "PGUSER": user,
                "PGPASSWORD": password,
                "PGHOST": host or "localhost",
                "PGPORT": port or "5432",
                "PGDATABASE": dbname.split("?", 1)[0],
            }
        )
    return env


def _run(command: list[str], database_url: str) -> str:
    argv = list(command)
    if argv and argv[0] == "bash":
        argv[0] = _bash_executable()
    result = subprocess.run(
        argv,
        cwd=ROOT,
        env=_bash_env(database_url),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.fail(result.stderr or result.stdout)
    return result.stdout


def _database_url() -> str | None:
    return os.environ.get("TRUELOCK_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


def test_migrations_seed_and_sql_invariants() -> None:
    """The forward-only runner, not raw SQL concatenation, owns idempotency."""
    database_url = _database_url()
    if not shutil.which("psql"):
        pytest.skip("requires psql — install postgresql-client and ensure it is on PATH")
    if not database_url:
        pytest.skip("requires TRUELOCK_TEST_DATABASE_URL or DATABASE_URL")

    first = _run(["bash", "scripts/migrate.sh"], database_url)
    second = _run(["bash", "scripts/migrate.sh"], database_url)
    _run(["bash", "scripts/seed_demo.sh"], database_url)
    seed_second = _run(["bash", "scripts/seed_demo.sh"], database_url)
    invariants = _run(["bash", "scripts/test_database.sh"], database_url)

    # Fresh DBs apply 0003; CI may have already migrated before pytest.
    assert (
        "apply 0003_canonical_contracts_and_master_data" in first
        or "skip 0003_canonical_contracts_and_master_data" in first
    )
    assert "skip 0003_canonical_contracts_and_master_data" in second
    assert "already exists" in seed_second
    assert "PASS" in invariants


def test_postgres_repositories_expose_canonical_cycle() -> None:
    database_url = _database_url()
    if not shutil.which("psql") or not database_url:
        pytest.skip("requires psql and DATABASE_URL")

    _run(["bash", "scripts/migrate.sh"], database_url)
    _run(["bash", "scripts/seed_demo.sh"], database_url)

    db = PostgresRepositories(database_url)
    try:
        root = db.transactions.get("TX-ROOT-001")
        hop = db.transactions.get("TX-HOP-001")
        ret = db.transactions.get("TX-RET-001")
        assert root is not None and root.amount == 1000000.0
        assert hop is not None and hop.amount == 920000.0
        assert ret is not None and ret.amount == 740000.0
        assert root.related_payment_id == "PMT-ROOT-001"
        payment = db.payments.get("PMT-ROOT-001")
        assert payment is not None
        assert "TX-ROOT-001" in payment.transaction_ids
        linked = db.transactions.list_for_payment("PMT-ROOT-001")
        assert [item.id for item in linked] == ["TX-ROOT-001"]
        provider = db.providers.get("LSF200820CC3")
        assert provider is not None
        assert provider.efos_status.value == "DEFINITIVE"
        leads = db.list_lead_records()
        assert any(lead.lead_id == "LEAD-CYCLE-TX-ROOT-001" for lead in leads)
    finally:
        db.close()


def test_import_pipeline_idempotent_and_auditable(tmp_path: Path) -> None:
    database_url = _database_url()
    if not shutil.which("psql") or not database_url:
        pytest.skip("requires psql and DATABASE_URL")

    _run(["bash", "scripts/migrate.sh"], database_url)
    _run(["bash", "scripts/seed_demo.sh"], database_url)

    # Unique SHA each run so prior suite imports do not short-circuit the first pass.
    # Mutate an already-invalid cell so row counts stay accepted=1 / rejected=1.
    bank_src = (FIXTURES / "bank" / "partial_invalid_rows.csv").read_text(encoding="utf-8")
    unique_bank = tmp_path / "partial_invalid_rows.csv"
    unique_bank.write_text(
        bank_src.replace("not-a-date", f"not-a-date-{os.urandom(4).hex()}"),
        encoding="utf-8",
    )
    efos_src = (FIXTURES / "efos" / "valid_69b.csv").read_text(encoding="utf-8")
    unique_efos = tmp_path / "valid_69b.csv"
    unique_efos.write_text(
        efos_src.replace("Servicios", f"Servicios-{os.urandom(3).hex()}"),
        encoding="utf-8",
    )

    db = PostgresRepositories(database_url)
    try:
        service = ImportService(db)
        first = service.import_bank_csv(unique_bank)
        assert first.accepted == 1
        assert first.rejected == 1
        assert first.rejections
        assert first.reused_prior_import is False

        second = service.import_bank_csv(unique_bank)
        assert second.reused_prior_import is True
        assert second.source_file_id == first.source_file_id
        assert second.rejected == first.rejected

        missing = service.import_bank_csv(FIXTURES / "bank" / "missing_required_column.csv")
        assert missing.accepted == 0
        assert missing.rejected == 1
        assert missing.rejections[0].error_code == "INGEST_ERROR"

        efos = service.import_efos_69b(unique_efos)
        assert efos.accepted == 1
        # Contextual import must not invent findings.
        findings_before = db.case_findings("CASE-DEMO-001")
        efos_again = service.import_efos_69b(unique_efos)
        assert efos_again.reused_prior_import is True
        assert db.case_findings("CASE-DEMO-001") == findings_before
    finally:
        db.close()


def test_investigation_service_persists_and_reloads_from_postgres() -> None:
    database_url = _database_url()
    if not shutil.which("psql") or not database_url:
        pytest.skip("requires psql and DATABASE_URL")

    _run(["bash", "scripts/migrate.sh"], database_url)
    _run(["bash", "scripts/seed_demo.sh"], database_url)

    db = PostgresRepositories(database_url)
    try:
        service = InvestigationService(database=db)
        # Seed already has an investigation for the cycle lead; reuse must be stable.
        first = service.start_investigation("LEAD-CYCLE-TX-ROOT-001")
        assert first["case"]["case_id"] == "CASE-DEMO-001"
        assert first["steps"]
        assert first["evidence"]

        service_reloaded = InvestigationService(database=PostgresRepositories(database_url))
        try:
            second = service_reloaded.start_investigation("LEAD-CYCLE-TX-ROOT-001")
            assert second["case"]["case_id"] == first["case"]["case_id"]
            assert [step["step_id"] for step in second["steps"]] == [
                step["step_id"] for step in first["steps"]
            ]
            assert [item["evidence_id"] for item in second["evidence"]] == [
                item["evidence_id"] for item in first["evidence"]
            ]
        finally:
            service_reloaded.database.close()  # type: ignore[union-attr]
    finally:
        db.close()
