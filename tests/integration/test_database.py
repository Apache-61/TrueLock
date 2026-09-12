"""Integration coverage for the PostgreSQL migrations and demo seed."""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
MIGRATIONS = sorted((ROOT / "database" / "migrations").glob("*.sql"))
SEEDS = sorted((ROOT / "database" / "seeds").glob("*.sql"))


def _run_psql(database_url: str, sql: str) -> str:
    result = subprocess.run(
        ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-At", "-f", "-"],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.fail(result.stderr or result.stdout)
    return result.stdout


def test_migrations_and_seed_are_repeatable() -> None:
    """Build a scratch schema, apply everything twice, and check fixture counts."""
    if not shutil.which("psql") or not os.environ.get("DATABASE_URL"):
        pytest.skip("requires psql and DATABASE_URL")

    database_url = os.environ["DATABASE_URL"]
    schema = f"truelock_test_{uuid.uuid4().hex}"
    migration_sql = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)
    seed_sql = "\n".join(path.read_text(encoding="utf-8") for path in SEEDS)
    setup = f"CREATE SCHEMA {schema}; SET search_path TO {schema};\n"
    teardown = f"DROP SCHEMA {schema} CASCADE;"
    try:
        _run_psql(database_url, setup + migration_sql + migration_sql + seed_sql + seed_sql)
        counts = _run_psql(
            database_url,
            f"SET search_path TO {schema};\n"
            "SELECT 'entities', count(*) FROM entities UNION ALL "
            "SELECT 'providers', count(*) FROM providers UNION ALL "
            "SELECT 'accounts', count(*) FROM accounts UNION ALL "
            "SELECT 'invoices', count(*) FROM invoices UNION ALL "
            "SELECT 'payments', count(*) FROM payments UNION ALL "
            "SELECT 'transactions', count(*) FROM transactions ORDER BY 1;",
        )
        assert counts.splitlines() == [
            "accounts|3",
            "entities|3",
            "invoices|1",
            "payments|1",
            "providers|1",
            "transactions|2",
        ]
    finally:
        _run_psql(database_url, teardown)
