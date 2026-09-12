"""Pull request assembly.

The body follows `.github/pull_request_template.md` section for section,
so a human reviewer sees the shape they expect, and adds the fields the
worker protocol requires on top: risks, which AI worker ran it, and the
decisions the change relates to.

A failed run still gets a PR -- as a **draft**, titled so the failure is
the first thing visible. Losing the work would be worse, and hiding the
failure is not an option: "NO crear PR como si todo estuviera correcto"
cuts both ways, and a draft marked FAILED is honest.
"""
from __future__ import annotations

from dataclasses import dataclass

from .scope import repo_relative
from .handoff import Handoff
from .tasks import TaskSpec

#: Paths that, when touched, are worth naming as a risk to the reviewer.
RISK_PATHS = {
    "domain/schemas/": "changes a frozen domain contract -- every module depends on it",
    "docs/contracts/": "changes an interface contract between modules",
    "database/migrations/": "changes the database schema",
    "ARCHITECTURE.md": "changes a frozen architectural decision",
    "SECURITY.md": "changes security policy",
    ".github/workflows/": "changes CI behaviour for every future PR",
    "orchestrator/policies/": "changes budget or provider policy",
}


def assess_risks(handoff: Handoff, task: TaskSpec, validation_ok: bool) -> list[str]:
    """Name the risks a reviewer should weigh, rather than asserting there are none."""
    risks: list[str] = []
    changed = list(handoff.result.changed_files) if handoff.result else []

    for path in changed:
        normalized = repo_relative(path)
        for prefix, reason in RISK_PATHS.items():
            if normalized.startswith(prefix):
                entry = f"`{normalized}` {reason}."
                if entry not in risks:
                    risks.append(entry)

    if not validation_ok:
        risks.append(
            "**Validation did not pass.** This PR is a draft and must not be "
            "merged until the failures below are resolved."
        )
    elif not handoff.validation_summary.startswith("PASSED"):
        risks.append(
            "**Nothing was verified.** Every validation gate was skipped, so "
            "this PR is a draft: no test actually ran against this change."
        )
    if handoff.scope_violations:
        risks.append(
            "The AI attempted changes outside the task's allowed_paths; see "
            "the scope section below."
        )
    if handoff.adr_required:
        risks.append(
            "Architectural surface was touched, so an ADR is required before merge."
        )
    if handoff.result and handoff.result.new_dependencies:
        risks.append(
            "New dependencies were introduced ("
            + ", ".join(handoff.result.new_dependencies)
            + "), which requires human authorization (CONTRIBUTING.md 5)."
        )
    if handoff.result and handoff.result.status == "PARTIAL":
        risks.append("The AI reported the task as PARTIAL, not DONE.")
    if not risks:
        risks.append(
            "No contract, schema, migration, security, or CI surface was touched, "
            "and validation passed. Normal review applies."
        )
    return risks


@dataclass
class PullRequestDraft:
    title: str
    body: str
    head: str
    base: str
    draft: bool


def build_pull_request(
    *,
    task: TaskSpec,
    handoff: Handoff,
    validation_ok: bool,
    base_branch: str,
    adapter_name: str,
    validation_verified: bool | None = None,
) -> PullRequestDraft:
    result = handoff.result
    changed = list(result.changed_files) if result else []
    tests = result.tests if result else None

    if validation_verified is None:
        validation_verified = validation_ok
    if not validation_ok:
        status_prefix = "[VALIDATION FAILED] "
    elif not validation_verified:
        status_prefix = "[UNVERIFIED] "
    else:
        status_prefix = ""
    title = f"{status_prefix}{task.task_id}: {task.title.split(':', 1)[-1].strip() or task.title}"

    checked = "x" if validation_verified else " "
    contract_untouched = not any(
        str(path).startswith(("domain/schemas/", "docs/contracts/")) for path in changed
    )

    body = f"""## Task

{task.task_id} — {task.title}
Issue: {task.html_url or '#' + str(task.issue_number)}
Task file: `tasks/` mirror for {task.task_id}

## Objective

{task.objective or '_Not stated on the issue._'}

## Summary

{(result.summary if result and result.summary else '_The AI worker returned no summary._')}

## Changed files / areas

{chr(10).join(f'- `{path}`' for path in changed) or '_No files changed._'}

Declared `allowed_paths` for this task:

{chr(10).join(f'- `{path}`' for path in task.allowed_paths) or '- _none declared_'}

{'**Scope violations detected:**' + chr(10) + chr(10) + chr(10).join(f'- {item}' for item in handoff.scope_violations) if handoff.scope_violations else 'All changed paths are inside the declared budget.'}

## Tests

- [{checked}] Ran the relevant test level(s) from `docs/testing.md`
- [{checked}] `pytest` passes locally
- Result: {handoff.validation_summary or 'not run'}

```
{(handoff.validation_detail or 'no validation output').strip()[-3000:]}
```

{f'Reported by the AI worker: passed={tests.passed}, failed={tests.failed}, skipped={tests.skipped}. {tests.details}'.strip() if tests else ''}

## Risks

{chr(10).join(f'- {risk}' for risk in assess_risks(handoff, task, validation_ok))}

## Contract impact

- [{'x' if contract_untouched else ' '}] This PR does **not** change any file under `domain/schemas/` or `docs/contracts/`
- [{' ' if contract_untouched else 'x'}] This PR **does** change a contract — human authorization required (`CONTRIBUTING.md` §5)

## Documentation updated

{chr(10).join(f'- `{item}`' for item in (result.documentation_changes if result else [])) or '- _No documentation changes reported._'}

## Related decisions

- `history/decisions/ADR-0003-task-coordination.md` — the claim protocol this run followed
{chr(10).join(f'- ADR required: `{trigger}` was touched' for trigger in handoff.adr_required)}

## AI worker

- worker_id: `{handoff.worker_id}`
- run_id: `{handoff.run_id}`
- adapter: `{adapter_name}`
- branch: `{handoff.branch}`
- history: `history/ai-activity/{handoff.history_filename()}`

{chr(10).join(handoff.routing_events)}

## Handoff

```json
{handoff.to_json().rstrip()}
```

---

This pull request was opened by an automated development worker
(`orchestrator/workers/`). It is **not** auto-merged: a human decides
(`CONTRIBUTING.md` §5).
"""
    return PullRequestDraft(
        title=title,
        body=body,
        head=handoff.branch,
        base=base_branch,
        draft=not validation_verified,
    )


def build_human_authorization_proposal(task: TaskSpec, *, worker_id: str, context_note: str = "") -> str:
    """What the worker posts instead of code when `execution:human` is set.

    The worker stops before touching any file. It offers an
    implementation plan a human can authorize, reject, or edit -- which
    is the entire point of the `execution:human` marker.
    """
    criteria = "\n".join(f"- [ ] {item}" for item in task.acceptance_criteria) or "- _none declared_"
    allowed = "\n".join(f"- `{path}`" for path in task.allowed_paths) or "- _none declared_"
    return f"""PROPOSAL (no code was written)

**worker_id:** {worker_id}
**task:** {task.task_id} — {task.title}

This task is marked `execution: human` (or `human_authorization: yes`), so
this worker **stopped before modifying any file**, per `CONTRIBUTING.md` §5.
What follows is a proposal for a human to authorize, amend, or reject.

## Why this needs a human

{task.objective or '_No objective stated on the issue._'}

Human authorization applies to: contract/schema changes, architecture
changes, new infrastructure or paid services, security policy, impactful
database migrations, the forensic agent's authority, demo deploys, and
merging high-risk PRs.

## Proposed scope

{allowed}

## Acceptance criteria this would have to meet

{criteria}

## What the worker would do once authorized

1. Claim the task (CLAIM → VERIFY, `tasks/README.md`).
2. Create `{task.branch_name}` from `main`.
3. Implement strictly inside the allowed paths above.
4. Run formatter, lint, type check, unit, contract and integration gates.
5. Write the handoff (`history/ai-activity/`) and open a PR — never merge it.

{context_note}

## To authorize

Reply on this issue confirming the scope, then either re-run the worker
with the task marked `execution:auto`, or implement it by hand. The
worker will not proceed on this task until that marker changes.
"""
