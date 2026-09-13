"""Optional Postgres E2E: seed → detect → investigate → API."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from truelock.api.app import create_app
from truelock.database.repositories.postgres import PostgresRepositories
from truelock.agent.gemini_client import GeminiClient
from truelock.services.investigation_service import InvestigationService

ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str | None:
    return os.environ.get("TRUELOCK_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


def _bash_executable() -> str:
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
    prefix_ok = database_url.startswith("postgresql://") or database_url.startswith("postgres://")
    if prefix_ok:
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


def _run(command: list[str], database_url: str) -> None:
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


@pytest.mark.skipif(not shutil.which("psql"), reason="requires psql")
def test_postgres_dataset_to_api() -> None:
    database_url = _database_url()
    if not database_url:
        pytest.skip("requires DATABASE_URL")

    _run(["bash", "scripts/migrate.sh"], database_url)
    _run(["bash", "scripts/seed_demo.sh"], database_url)

    db = PostgresRepositories(database_url)
    service = InvestigationService(database=db, gemini_client=GeminiClient(api_key=""))
    leads = service.list_leads()
    assert leads
    cycle = next(
        (l for l in leads if "CYCLE" in l.detector_id or "ROUND" in l.detector_id),
        max(leads, key=lambda item: item.risk_score),
    )
    result = service.start_investigation(cycle.lead_id)
    assert result["case"]
    assert result["evidence"]

    # App with DB uses settings; force DB path via env for this process
    os.environ["DATABASE_URL"] = database_url
    client = TestClient(create_app(use_database=True))
    api_leads = client.get("/api/leads").json()
    assert api_leads
    case_id = result["case"]["case_id"] if isinstance(result["case"], dict) else result["case"].case_id
    details = client.get(f"/api/investigations/{case_id}").json()
    assert details.get("case") or details.get("steps") is not None
