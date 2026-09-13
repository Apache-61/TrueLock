"""Integration coverage for the PostgreSQL migrations and demo seed."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]


def _run(command: list[str], database_url: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.fail(result.stderr or result.stdout)
    return result.stdout


def test_migrations_seed_and_sql_invariants() -> None:
    """The forward-only runner, not raw SQL concatenation, owns idempotency."""
    database_url = os.environ.get("TRUELOCK_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not shutil.which("psql"):
        pytest.skip("requires psql — install postgresql-client and ensure it is on PATH")
    if not database_url:
        pytest.skip("requires TRUELOCK_TEST_DATABASE_URL or DATABASE_URL")

    first = _run(["bash", "scripts/migrate.sh"], database_url)
    second = _run(["bash", "scripts/migrate.sh"], database_url)
    _run(["bash", "scripts/seed_demo.sh"], database_url)
    seed_second = _run(["bash", "scripts/seed_demo.sh"], database_url)
    invariants = _run(["bash", "scripts/test_database.sh"], database_url)

    assert "apply 0003_canonical_contracts_and_master_data" in first
    assert "skip 0003_canonical_contracts_and_master_data" in second
    assert "already exists" in seed_second
    assert "PASS" in invariants
