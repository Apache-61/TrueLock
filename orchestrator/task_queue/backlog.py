"""The real implementation backlog, as data.

Why a Python module and not YAML or forty hand-written Markdown files:

* **One source of truth.** `tasks/*/TASK-###.md` (the human-readable
  mirror) and the GitHub issues (the machine-readable queue, ADR-0003)
  are both *rendered* from here by
  `scripts/orchestration/seed_backlog.py`. Hand-maintaining forty files
  in two places is how a mirror drifts from its queue.
* **The dependency graph is checkable.** `validate()` refuses a
  dependency on a task that does not exist and refuses a cycle. A queue
  whose graph has a cycle deadlocks every worker at once, silently:
  each task waits for a dependency that will never be satisfied, and
  `worker status` reports "no eligible task" on all four machines with
  no hint as to why.
* **No new dependency.** The worker has to start on a fresh machine
  without `pip install` (see `orchestrator/routing/router.py` on why
  PyYAML is optional). stdlib only.

The rendered issue body deliberately matches the dialect that
`orchestrator/workers/tasks.py::parse_issue` reads -- ``- **type:**``
fields, fenced ``## Allowed paths`` blocks, ``## Acceptance criteria``
checkboxes. `tests/unit/test_backlog.py` asserts that round trip rather
than trusting the two files to stay in step.

Granularity rule (`CONTRIBUTING.md` 4): one primary responsibility, a
bounded file scope, explicit dependencies, testable acceptance criteria.
"Implement GET /investigations/{id}", not "build the backend".

Scope overlap rule: two tasks that can be claimed at the same time (same
dependency depth) must not declare overlapping `allowed_paths`. Four
machines working concurrently in overlapping paths produce merge
conflicts that no amount of claim protocol prevents. `validate()`
enforces this.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDefinition:
    """One unit of authorized work, before it becomes an issue."""

    task_id: str
    title: str
    priority: str
    area: str
    objective: str
    allowed_paths: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    tests_required: str
    task_type: str = "feature"
    depends_on: tuple[str, ...] = ()
    #: Where this task may write its tests. Every task is *required* to
    #: bring tests, so every task must be scoped to write them -- without
    #: this the worker's own scope guard blocks the tests the task asks
    #: for, on every task, and each one stops BLOCKED for a violation it
    #: was instructed to commit.
    test_paths: tuple[str, ...] = ("tests/**",)
    forbidden_paths: tuple[str, ...] = ()
    documentation_requirements: str = ""
    execution_mode: str = "auto"
    human_authorization: bool = False
    status: str = "READY"
    #: Set for the tasks seeded during bootstrap, whose issues already
    #: exist. The seeder updates those in place instead of creating a
    #: duplicate.
    existing_issue: int = 0

    @property
    def number(self) -> int:
        return int(self.task_id.split("-")[1])

    @property
    def slug(self) -> str:
        words = [
            word
            for word in "".join(
                character.lower() if character.isalnum() else " "
                for character in self.title
            ).split()
        ]
        return "-".join(words[:6])

    @property
    def mirror_filename(self) -> str:
        return f"{self.task_id}-{self.slug}.md"

    @property
    def labels(self) -> list[str]:
        """The labels `scripts/setup/create_labels.sh` creates."""
        status_label = {
            "READY": "status:ready",
            "RESEARCH": "status:research",
            "PROPOSAL": "status:research",
            "WAITING_AUTHORIZATION": "status:blocked",
            "BLOCKED": "status:blocked",
            "MERGED": "status:done",
        }.get(self.status, "status:ready")
        task_type = "type:docs" if self.task_type == "documentation" else f"type:{self.task_type}"
        return [
            task_type,
            f"priority:{self.priority}",
            status_label,
            f"area:{self.area}",
            f"execution:{self.execution_mode}",
        ]

    def render_markdown(self) -> str:
        """The mirror file *and* the issue body: one dialect, one render.

        Kept byte-identical between the two on purpose. When a worker
        reads the issue and a human reads `tasks/ready/`, they must be
        reading the same task.
        """
        depends = ", ".join(self.depends_on) if self.depends_on else "none"
        authorization = "yes" if self.human_authorization else "no"
        lines = [
            f"# {self.task_id}: {self.title}",
            "",
            f"- **type:** {self.task_type}",
            f"- **priority:** {self.priority}",
            f"- **status:** {self.status}",
            f"- **execution_mode:** {self.execution_mode}",
            f"- **owner (area):** {self.area}",
            f"- **depends_on:** {depends}",
            f"- **human_authorization:** {authorization}",
            "",
            "## Objective",
            "",
            self.objective.strip(),
            "",
            "## Allowed paths",
            "",
            "```",
            *self.allowed_paths,
            *self.test_paths,
            "```",
            "",
        ]
        if self.forbidden_paths:
            lines += ["## Forbidden paths", "", "```", *self.forbidden_paths, "```", ""]
        lines += ["## Acceptance criteria", ""]
        lines += [f"- [ ] {criterion}" for criterion in self.acceptance_criteria]
        lines += ["", "## Tests required", "", self.tests_required.strip(), ""]
        if self.documentation_requirements:
            lines += [
                "## Documentation requirements",
                "",
                self.documentation_requirements.strip(),
                "",
            ]
        return "\n".join(lines).rstrip() + "\n"


class BacklogError(ValueError):
    """The backlog is internally inconsistent and must not be seeded."""


def by_id(tasks: tuple[TaskDefinition, ...] | None = None) -> dict[str, TaskDefinition]:
    return {task.task_id: task for task in (tasks if tasks is not None else BACKLOG)}


def depth(task_id: str, index: dict[str, TaskDefinition], _seen: frozenset[str] = frozenset()) -> int:
    """How many dependency hops before this task can start.

    Depth 0 means "claimable right now". Used to spot the waves in which
    work actually becomes available, and by `validate()` to compare the
    scopes of tasks that can run at the same time.
    """
    if task_id in _seen:
        raise BacklogError(f"dependency cycle reached {task_id}")
    task = index.get(task_id)
    if task is None or not task.depends_on:
        return 0
    return 1 + max(
        depth(dependency, index, _seen | {task_id}) for dependency in task.depends_on
    )


def _globs_overlap(left: str, right: str) -> bool:
    """Do two path globs plausibly cover a common file?

    Deliberately conservative -- it compares the fixed prefix before the
    first wildcard, so `detection/rules/**` and `detection/**` count as
    overlapping. A false positive costs one scope edit; a false negative
    costs a merge conflict between two machines at 3am.
    """
    left_prefix = left.split("*")[0].rstrip("/")
    right_prefix = right.split("*")[0].rstrip("/")
    if not left_prefix or not right_prefix:
        return True
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
    )


def validate(tasks: tuple[TaskDefinition, ...] | None = None) -> list[str]:
    """Every way this backlog could deadlock or collide. Empty == good."""
    tasks = tasks if tasks is not None else BACKLOG
    index = by_id(tasks)
    problems: list[str] = []

    seen: set[str] = set()
    for task in tasks:
        if task.task_id in seen:
            problems.append(f"{task.task_id}: duplicate task id")
        seen.add(task.task_id)

    for task in tasks:
        for dependency in task.depends_on:
            if dependency not in index:
                problems.append(
                    f"{task.task_id}: depends on {dependency}, which is not in the backlog"
                )
            if dependency == task.task_id:
                problems.append(f"{task.task_id}: depends on itself")

    # Cycles: a cycle means every task on it waits forever, and the
    # worker reports only "unmet dependencies" with no hint why.
    for task in tasks:
        try:
            depth(task.task_id, index)
        except BacklogError as error:
            problems.append(f"{task.task_id}: {error}")
        except RecursionError:
            problems.append(f"{task.task_id}: dependency graph is too deep or cyclic")

    if problems:
        # Scope comparison below needs a sane graph to compute depth.
        return problems

    # Concurrent-scope collisions. Two tasks can be claimed at the same
    # moment unless one transitively depends on the other -- depth alone
    # is not enough, because a depth-0 task with no dependants is still
    # in flight while depth-3 work runs on another machine. Anything
    # genuinely unorderable must therefore own disjoint paths, or carry
    # a dependency edge that serialises it.
    ancestors: dict[str, set[str]] = {}

    def all_dependencies(task_id: str) -> set[str]:
        if task_id in ancestors:
            return ancestors[task_id]
        ancestors[task_id] = set()  # guards against re-entry
        collected: set[str] = set()
        for dependency in index[task_id].depends_on if task_id in index else ():
            collected.add(dependency)
            collected |= all_dependencies(dependency)
        ancestors[task_id] = collected
        return collected

    ordered = sorted(tasks, key=lambda item: item.number)
    for outer_position, outer in enumerate(ordered):
        for inner in ordered[outer_position + 1 :]:
            if inner.task_id in all_dependencies(outer.task_id):
                continue
            if outer.task_id in all_dependencies(inner.task_id):
                continue
            # Source scope only. Test paths are deliberately excluded:
            # every task writes tests, each into its own named file, and
            # a clash there is a rename rather than a lost change. The
            # conflict worth blocking is two tasks editing one module.
            collisions = sorted(
                (left, right)
                for left in outer.allowed_paths
                for right in inner.allowed_paths
                if _globs_overlap(left, right)
            )
            if collisions:
                left, right = collisions[0]
                problems.append(
                    f"{outer.task_id} and {inner.task_id} have no dependency between them "
                    f"so they can run concurrently, but both write {left!r} / {right!r}"
                )
    return problems


def ready_now(tasks: tuple[TaskDefinition, ...] | None = None) -> list[TaskDefinition]:
    """Tasks with no unmet dependency -- what a fresh worker can claim."""
    tasks = tasks if tasks is not None else BACKLOG
    return [task for task in tasks if not task.depends_on and task.status == "READY"]


def render_graph(tasks: tuple[TaskDefinition, ...] | None = None) -> str:
    """The dependency graph, as a Mermaid diagram for `tasks/BACKLOG.md`."""
    tasks = tasks if tasks is not None else BACKLOG
    index = by_id(tasks)
    lines = ["```mermaid", "graph LR"]
    for task in sorted(tasks, key=lambda item: item.number):
        lines.append(f'  {task.task_id.replace("-", "")}["{task.task_id}<br/>{task.title}"]')
    for task in sorted(tasks, key=lambda item: item.number):
        for dependency in task.depends_on:
            if dependency in index:
                lines.append(
                    f'  {dependency.replace("-", "")} --> {task.task_id.replace("-", "")}'
                )
    lines.append("```")
    return "\n".join(lines)


#: The real implementation backlog.
#:
#: TASK-001..007 were seeded during bootstrap and already have issues;
#: they carry `existing_issue` so the seeder updates them in place rather
#: than opening duplicates. Everything from TASK-008 is new work derived
#: from the product core in the operating pack:
#:
#:   DATA -> NORMALIZATION -> DETERMINISTIC DETECTION -> LEADS ->
#:   INVESTIGATION TOOLS -> AI INVESTIGATOR -> EVIDENCE -> CASE ->
#:   FRONTEND -> Q&A
_SPINE: tuple[TaskDefinition, ...] = (
    # ---------------- spine (issues #1-#7 already exist) -------------
    TaskDefinition(
        task_id="TASK-001",
        existing_issue=1,
        title="Canonical domain data ingestion & normalization",
        priority="P0",
        area="data",
        objective=(
            "Implement `domain/entities/` (Pydantic models matching "
            "`domain/schemas/`) and `scripts/ingest/` normalizers that turn raw "
            "CFDI/CSV-style records into canonical "
            "`Provider`/`Invoice`/`Payment`/`Transaction`/`Account` objects, plus "
            "the repository interfaces in `backend/repositories/` that every "
            "later module reads through.\n\n"
            "Input: `domain/schemas/*.schema.json`, `docs/contracts/domain.md`. "
            "The schemas are a frozen contract -- implement them, do not edit them."
        ),
        allowed_paths=(
            "domain/entities/**",
            "scripts/ingest/**",
            "backend/repositories/**",
            # The entities are Pydantic models (ARCHITECTURE.md), and a
            # task cannot deliver them without declaring the dependency.
            "requirements.txt",
            "requirements-dev.txt",
        ),
        forbidden_paths=("domain/schemas/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "Every schema in `domain/schemas/` for a canonical entity has a "
            "corresponding entity class.",
            "A malformed record is rejected with a clear error, not "
            "best-effort-guessed (`SECURITY.md`).",
            "Round-trips: entity -> dict -> entity produces an identical object.",
            "`backend/repositories/` exposes a read interface per entity that "
            "later modules can depend on without importing the database driver.",
        ),
        tests_required=(
            "`tests/unit/` for each entity's validation; `tests/contract/` checks "
            "the entity's serialized shape matches its JSON Schema."
        ),
        documentation_requirements="Update `domain/entities/README.md` with what is implemented.",
    ),
    TaskDefinition(
        task_id="TASK-002",
        existing_issue=2,
        title="Database migration & seed fixtures",
        priority="P0",
        area="database",
        depends_on=("TASK-001",),
        objective=(
            "Stand up PostgreSQL from `database/migrations/0001_init.sql`, add any "
            "missing migration needed once TASK-001's entities are final, and load "
            "`database/seeds/` with fixture data.\n\n"
            "A structural change to the draft schema touches a shared contract and "
            "needs human sign-off first (`CONTRIBUTING.md` 5)."
        ),
        allowed_paths=("database/**",),
        forbidden_paths=("domain/schemas/**", "frontend/**", "agent/**"),
        acceptance_criteria=(
            "A clean database can be built from migrations alone, in order, "
            "with no manual step.",
            "Migrations are idempotent to re-run and each has a documented "
            "forward path.",
            "`database/seeds/` loads without error against the migrated schema.",
            "Every canonical entity from TASK-001 has a table whose columns match "
            "the entity's fields.",
        ),
        tests_required=(
            "`tests/integration/` builds a scratch database from migrations and "
            "asserts the seed load succeeds and row counts match the fixtures."
        ),
        documentation_requirements="Update `database/README.md` and `database/migrations/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-003",
        existing_issue=3,
        title="Synthetic scenario generator + answer keys",
        priority="P0",
        area="data",
        depends_on=("TASK-001",),
        objective=(
            "Build a generator producing at least three fraud scenarios "
            "(duplicate-like case, cycle case, fan-in/fan-out case) as canonical "
            "fixtures, each with an answer key that is hidden from the agent. Use "
            "AMLSim-style patterns (`research/fraud/README.md`) plus at least one "
            "hand-built shell-company/kickback ring grounded in the SAT/CFDI domain "
            "(`docs/regulatory/`).\n\n"
            "Reads `domain/entities/` -- does not modify it."
        ),
        allowed_paths=("data/synthetic/**", "data/answer_keys/**", "data/fixtures/**"),
        forbidden_paths=("domain/schemas/**", "detection/**", "agent/**", "frontend/**"),
        acceptance_criteria=(
            "At least three distinct scenarios generate deterministically from a "
            "seed, so a run is reproducible.",
            "Each scenario ships an answer key naming the entities and the "
            "specific records that constitute the fraud.",
            "Answer keys live under `data/answer_keys/` and are never read by "
            "detection or agent code -- only by tests.",
            "Generated records validate against the canonical entities from TASK-001.",
            "The generator emits clean (non-fraudulent) background volume too, so "
            "a detector that flags everything fails visibly.",
        ),
        tests_required=(
            "`tests/scenarios/` asserts each generated scenario validates and that "
            "the answer key references records that actually exist in the fixture."
        ),
        documentation_requirements="Document each scenario and its fraud pattern in `data/synthetic/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-004",
        existing_issue=4,
        title="Detector framework + first three detectors",
        priority="P0",
        area="detection",
        depends_on=("TASK-001", "TASK-003"),
        objective=(
            "Implement the detector interface (`docs/contracts/detector.md`), the "
            "registry, and the first three detectors: `DUPLICATE_INVOICE`, "
            "`INVOICE_PAYMENT_MISMATCH`, `69B_CORRELATION` "
            "(`docs/detection/rules.md`). Implement `detection/scoring/` to turn "
            "signals into `Lead`s with a documented, tunable threshold.\n\n"
            "This task owns the framework every later detector plugs into, so keep "
            "the interface small and the registry open: a new detector must be "
            "addable as one new file plus one registry entry."
        ),
        allowed_paths=(
            "detection/rules/__init__.py",
            "detection/rules/base.py",
            "detection/rules/duplicate_invoice.py",
            "detection/rules/invoice_payment_mismatch.py",
            "detection/rules/efos_correlation.py",
            "detection/scoring/**",
        ),
        forbidden_paths=("frontend/**", "agent/**", "domain/schemas/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "A detector is one class implementing the documented interface, "
            "registered in one place.",
            "Every signal carries the source record ids that justify it -- a signal "
            "with no provenance is a bug.",
            "Detectors are pure over their input: same input, same signals, no "
            "database or network access of their own.",
            "Each of the three detectors fires on its scenario from TASK-003 and "
            "stays silent on the clean background volume.",
            "`detection/scoring/` produces `Lead`s with a documented threshold and "
            "an explanation of why the lead scored as it did.",
        ),
        tests_required=(
            "`tests/unit/` per detector for the rule logic; `tests/scenarios/` "
            "asserts each detector's findings against the TASK-003 answer keys "
            "(precision and recall, not just 'it ran')."
        ),
        documentation_requirements="Update `detection/README.md` and `docs/detection/rules.md` with the implemented rules.",
    ),
    TaskDefinition(
        task_id="TASK-005",
        existing_issue=5,
        title="Agent tool layer + tool schemas",
        priority="P0",
        area="agent",
        depends_on=("TASK-009",),
        objective=(
            "Implement the read-only tool layer from `docs/contracts/agent-tools.md`: "
            "the `ToolResult` contract "
            "(`result`/`provenance`/`source_ids`/`execution_time`/`errors`), the "
            "tool registry, the machine-readable tool schemas the model is given, "
            "and the first two concrete tools "
            "(`get_entity_profile`, `list_leads`).\n\n"
            "Remaining tools are separate tasks that plug into this layer. Tools "
            "read through `backend/repositories/` -- they never reshape the database."
        ),
        allowed_paths=(
            "agent/tools/__init__.py",
            "agent/tools/base.py",
            "agent/tools/schemas.py",
            "agent/tools/registry.py",
            "agent/tools/entity_profile.py",
            "agent/tools/leads.py",
        ),
        forbidden_paths=("database/**", "frontend/**", "detection/**", "domain/schemas/**"),
        acceptance_criteria=(
            "Every tool returns the documented `ToolResult` shape, including on "
            "error -- a failing tool returns an error result, it does not raise "
            "into the agent loop.",
            "Every tool result carries `source_ids` that trace back to real records.",
            "Tool schemas are generated from the tool definitions, so a schema "
            "cannot drift from the function it describes.",
            "Tools are read-only: no tool writes to the database.",
            "A tool that would return an unbounded result set paginates or caps, "
            "and says so in the result.",
        ),
        tests_required=(
            "`tests/unit/` for the registry and the `ToolResult` contract; "
            "`tests/contract/` asserts every registered tool's schema matches its "
            "signature."
        ),
        documentation_requirements="Update `agent/tools/README.md` with the implemented tools and how to add one.",
    ),
    TaskDefinition(
        task_id="TASK-006",
        existing_issue=6,
        title="Frontend shell against mocked API",
        priority="P0",
        area="frontend",
        objective=(
            "Stand up the Next.js/TypeScript shell for the screens in "
            "`docs/demo/runbook.md` -- dashboard, investigation view, graph, money "
            "trail, evidence, case file, Q&A -- wired to a mock implementation of "
            "`docs/contracts/api.md` (static fixtures, no real backend needed).\n\n"
            "This task owns the shell: routing, layout, the API client seam, and "
            "the mock. Each screen's real content is a separate task that fills in "
            "its own route directory."
        ),
        allowed_paths=("frontend/**",),
        forbidden_paths=("domain/**", "detection/**", "database/**", "agent/**"),
        acceptance_criteria=(
            "`npm run build` and `npm run lint` succeed from a clean checkout.",
            "Every screen in the demo runbook has a route that renders from mock "
            "data.",
            "The API client is a single seam: swapping mock for real is a "
            "configuration change, not a rewrite of the screens.",
            "Mock fixtures match the shapes in `docs/contracts/api.md`.",
        ),
        tests_required="Component/route smoke tests that each screen renders from the mock without error.",
        documentation_requirements="Update `frontend/README.md` with how to run the shell and where the mock lives.",
    ),
    TaskDefinition(
        task_id="TASK-007",
        existing_issue=7,
        title="Orchestrator worker adapters",
        priority="P0",
        area="orchestrator",
        status="MERGED",
        objective="AI development worker MVP. Merged in PR #9.",
        allowed_paths=("orchestrator/workers/**",),
        acceptance_criteria=("Merged.",),
        tests_required="352 tests pass.",
    ),
)


#: DOMAIN -- the investigation-side entities the agent and case file need.
_DOMAIN: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-008",
        title="Investigation-layer entities: Lead, Evidence, InvestigationStep, Case",
        priority="P0",
        area="backend",
        depends_on=("TASK-001",),
        objective=(
            "Implement the entity classes for the investigation half of the domain, "
            "matching the frozen schemas: `lead.schema.json`, `evidence.schema.json`, "
            "`investigation_step.schema.json`, `case.schema.json`, "
            "`detector_signal.schema.json`.\n\n"
            "These are the types every later module exchanges: detectors emit "
            "`DetectorSignal` and `Lead`, the agent emits `InvestigationStep` and "
            "`Evidence`, case generation emits `Case`. Get the shapes right here and "
            "the rest of the system has a common vocabulary."
        ),
        allowed_paths=("domain/entities/**",),
        forbidden_paths=("domain/schemas/**", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Every investigation-side schema has a corresponding entity class.",
            "Round-trips: entity -> dict -> entity produces an identical object.",
            "An `Evidence` object cannot be constructed without provenance -- the "
            "type system enforces what `docs/contracts/evidence.md` requires.",
            "A `Case` composes `Lead`, `Evidence` and `InvestigationStep` rather "
            "than duplicating their fields.",
        ),
        tests_required=(
            "`tests/unit/` per entity; `tests/contract/` asserts each entity's "
            "serialized shape matches its JSON Schema."
        ),
        documentation_requirements="Update `domain/entities/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-009",
        title="Investigation persistence repositories",
        priority="P0",
        area="backend",
        depends_on=("TASK-002", "TASK-008"),
        objective=(
            "Persist the investigation-layer entities: migrations for leads, "
            "evidence, investigation steps and cases, plus the repository "
            "implementations that read and write them.\n\n"
            "The agent's investigation state (TASK-020) and the API (TASK-035) both "
            "depend on this being the single place investigation data is stored."
        ),
        allowed_paths=("backend/repositories/**", "database/migrations/**"),
        forbidden_paths=("domain/schemas/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "Leads, evidence, investigation steps and cases each round-trip through "
            "the database unchanged.",
            "An investigation's steps come back in the order they were recorded.",
            "Migrations follow TASK-002's conventions and re-run cleanly.",
            "Repositories expose the queries the agent tools actually need, rather "
            "than a generic ORM surface.",
        ),
        tests_required="`tests/integration/` round-trips each entity against a scratch database.",
        documentation_requirements="Update `backend/repositories/README.md`.",
    ),
)


#: DATA -- fixtures and the loader that gets them into the database.
_DATA: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-010",
        title="Seed loader: synthetic scenarios into the database",
        priority="P0",
        area="data",
        depends_on=("TASK-002", "TASK-003"),
        objective=(
            "A single command that loads a generated scenario from TASK-003 into "
            "the database built by TASK-002, so every developer and every demo "
            "starts from an identical, named dataset.\n\n"
            "This is the join between 'we can generate data' and 'the product has "
            "data to work on' -- it is on the critical path to the vertical slice."
        ),
        allowed_paths=("scripts/ingest/load_scenario.py", "database/seeds/**"),
        forbidden_paths=("domain/schemas/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "`load_scenario --scenario <name>` populates an empty database end to "
            "end with no manual step.",
            "Loading is idempotent: running it twice does not duplicate rows.",
            "The loader refuses to run against a database with existing data unless "
            "explicitly told to reset, so nobody destroys a working demo by accident.",
            "Answer keys are NOT loaded into the database -- they stay test-only.",
            "Load time for the demo scenario is reported, and is fast enough to "
            "re-run during the demo.",
        ),
        tests_required="`tests/integration/` loads a scenario into a scratch database and asserts row counts against the fixture.",
        documentation_requirements="Document the load command in `database/README.md` and `docs/demo/runbook.md`.",
    ),
    TaskDefinition(
        task_id="TASK-011",
        title="SAT 69-B EFOS list ingestion & enrichment",
        priority="P1",
        area="data",
        depends_on=("TASK-001",),
        objective=(
            "Ingest the SAT 69-B EFOS list (`docs/regulatory/sat-69b.md`) and expose "
            "an enrichment lookup that answers 'is this RFC listed, in what status, "
            "as of when'.\n\n"
            "The 69-B correlation detector in TASK-004 needs this to be more than a "
            "stub. Work from a local fixture copy of the list so the demo never "
            "depends on a live SAT endpoint."
        ),
        allowed_paths=("scripts/ingest/efos.py", "data/raw/efos/**"),
        forbidden_paths=("domain/schemas/**", "detection/**", "frontend/**", "agent/**"),
        acceptance_criteria=(
            "An RFC lookup returns the listed status and the date it applied.",
            "The status enum matches `domain/enums/efos-status.md` exactly.",
            "Lookup is against a local snapshot -- no network call at demo time.",
            "An unknown RFC returns 'not listed' rather than raising.",
        ),
        tests_required="`tests/unit/` for the lookup, including an RFC in each status and an unknown RFC.",
        documentation_requirements="Record the snapshot's provenance and date in `data/raw/efos/README.md`.",
    ),
)


#: DETECTION -- one detector per task, all plugging into TASK-004's registry.
_DETECTION: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-012",
        title="Money-flow graph engine",
        priority="P0",
        area="graph",
        depends_on=("TASK-001",),
        objective=(
            "Build the NetworkX-backed graph the money-flow detectors and the "
            "agent's tracing tools both run on: nodes for entities and accounts, "
            "edges for payments and transactions, each edge carrying amount, date "
            "and the source record id.\n\n"
            "This is shared infrastructure. Keep the construction separate from any "
            "single analysis so fan-in, fan-out, cycles and pass-through can each be "
            "one small module on top (TASK-015..018)."
        ),
        allowed_paths=("detection/graph/__init__.py", "detection/graph/builder.py", "detection/graph/model.py"),
        forbidden_paths=("frontend/**", "agent/**", "domain/schemas/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "A graph builds from canonical entities with no database access of its "
            "own -- it takes records, it does not fetch them.",
            "Every edge carries the source record id, so any path found can be "
            "traced back to evidence.",
            "Building the demo-scale graph is fast enough to do on request "
            "(document the measured time).",
            "Graph construction is deterministic: same records, same graph.",
        ),
        tests_required="`tests/unit/` for construction from a known fixture; assert node/edge counts and edge provenance.",
        documentation_requirements="Update `detection/graph/README.md` with the node/edge model.",
    ),
    TaskDefinition(
        task_id="TASK-013",
        title="Duplicate payment detector",
        priority="P0",
        area="detection",
        depends_on=("TASK-004",),
        objective=(
            "Detect the same payment made more than once -- same beneficiary, "
            "near-identical amount, close in time, distinct payment records -- as a "
            "detector plugged into the TASK-004 registry.\n\n"
            "Distinct from DUPLICATE_INVOICE: that one catches the same invoice "
            "billed twice, this one catches one invoice paid twice."
        ),
        allowed_paths=("detection/rules/duplicate_payment.py",),
        forbidden_paths=("detection/rules/base.py", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "Fires on the duplicate-payment scenario and stays silent on clean "
            "background volume.",
            "The tolerance window (amount and date) is a documented, tunable "
            "parameter, not a magic number in the middle of the rule.",
            "A legitimate instalment schedule does not fire -- document how the rule "
            "distinguishes it.",
            "Every signal names the specific payment record ids involved.",
        ),
        tests_required="`tests/unit/` for the rule; `tests/scenarios/` against the TASK-003 answer key.",
        documentation_requirements="Add the rule to `docs/detection/rules.md`.",
    ),
    TaskDefinition(
        task_id="TASK-014",
        title="Unusual amount detector",
        priority="P1",
        area="detection",
        depends_on=("TASK-004",),
        objective=(
            "Flag amounts that are anomalous for the supplier or the category: "
            "round-number outliers, amounts just under an approval threshold, and "
            "statistical outliers against that supplier's own history.\n\n"
            "Just-under-threshold is the highest-signal of the three in procurement "
            "fraud -- treat it as a first-class rule, not a footnote."
        ),
        allowed_paths=("detection/rules/unusual_amount.py",),
        forbidden_paths=("detection/rules/base.py", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "Thresholds are configurable and documented, with the reasoning for the "
            "defaults.",
            "A supplier with a short history does not produce false outliers -- "
            "document the minimum sample size.",
            "Just-under-approval-threshold amounts are flagged as their own signal "
            "type.",
            "Every signal names the records and states the comparison that made the "
            "amount unusual.",
        ),
        tests_required="`tests/unit/` covering each sub-rule; `tests/scenarios/` for precision on clean data.",
        documentation_requirements="Add the rule to `docs/detection/rules.md`.",
    ),
    TaskDefinition(
        task_id="TASK-015",
        title="Supplier concentration detector",
        priority="P1",
        area="detection",
        depends_on=("TASK-004",),
        objective=(
            "Detect concentration risk: a supplier taking an outsized share of a "
            "buyer's spend, a supplier created shortly before winning volume, or a "
            "buyer whose spend is split across suppliers that share an address, "
            "phone or bank account."
        ),
        allowed_paths=("detection/rules/supplier_concentration.py",),
        forbidden_paths=("detection/rules/base.py", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "Concentration is measured over a documented window, not all-time.",
            "Shared-identity detection (address/phone/account) names which "
            "attribute matched.",
            "A genuinely single-supplier category does not fire -- document how.",
            "Every signal names the supplier and buyer record ids.",
        ),
        tests_required="`tests/unit/` per sub-rule; `tests/scenarios/` against the answer key.",
        documentation_requirements="Add the rule to `docs/detection/rules.md`.",
    ),
    TaskDefinition(
        task_id="TASK-016",
        title="Fan-in / fan-out money-flow detector",
        priority="P0",
        area="graph",
        depends_on=("TASK-004", "TASK-012"),
        objective=(
            "On the TASK-012 graph, detect fan-in (many sources converging on one "
            "account in a short window) and fan-out (one source dispersing to many "
            "accounts), the classic layering shapes from `research/fraud/`.\n\n"
            "Emit detector signals through the TASK-004 registry so leads are scored "
            "the same way as every other rule."
        ),
        allowed_paths=("detection/graph/fan_patterns.py", "detection/rules/fan_patterns.py"),
        forbidden_paths=("detection/graph/builder.py", "detection/rules/base.py", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "Fan-in and fan-out are separately identifiable signal types.",
            "The degree and time-window thresholds are documented and tunable.",
            "A payroll or tax account with naturally high degree does not fire -- "
            "document the exclusion.",
            "Each signal names the centre account and the counterparty record ids.",
        ),
        tests_required="`tests/unit/` on a hand-built graph; `tests/scenarios/` against the fan-in/fan-out answer key.",
        documentation_requirements="Add the patterns to `docs/detection/rules.md` and `detection/graph/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-017",
        title="Cycle detection (circular money flow)",
        priority="P0",
        area="graph",
        depends_on=("TASK-004", "TASK-012"),
        objective=(
            "Detect money returning to its origin through intermediaries -- the "
            "round-trip that distinguishes a kickback ring from ordinary trade -- by "
            "finding cycles in the TASK-012 graph."
        ),
        allowed_paths=("detection/graph/cycles.py", "detection/rules/cycles.py"),
        forbidden_paths=("detection/graph/builder.py", "detection/rules/base.py", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "Cycles up to a documented maximum length are found; the bound exists so "
            "the search cannot blow up on the demo dataset.",
            "Cycle search completes within a documented time budget on the demo "
            "graph.",
            "A cycle signal reports the ordered path and the amount retained at each "
            "hop.",
            "Ordinary two-party back-and-forth trade is distinguished from a "
            "laundering cycle -- document the rule.",
        ),
        tests_required="`tests/unit/` on graphs with known cycles and known acyclic cases; `tests/scenarios/` against the cycle answer key.",
        documentation_requirements="Add the rule to `docs/detection/rules.md`.",
    ),
    TaskDefinition(
        task_id="TASK-018",
        title="Rapid pass-through detector",
        priority="P1",
        area="graph",
        depends_on=("TASK-004", "TASK-012"),
        objective=(
            "Detect accounts that receive and forward substantially the same amount "
            "within a short window while retaining little -- the signature of a "
            "conduit or shell account rather than a real operating business."
        ),
        allowed_paths=("detection/graph/pass_through.py", "detection/rules/pass_through.py"),
        forbidden_paths=("detection/graph/builder.py", "detection/rules/base.py", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "The retention ratio and time window are documented, tunable parameters.",
            "A signal reports the in-edge, the out-edge, the elapsed time and the "
            "retained fraction.",
            "A normal business with fast supplier settlement does not fire -- "
            "document how it is excluded.",
        ),
        tests_required="`tests/unit/` on hand-built flows; `tests/scenarios/` against the answer key.",
        documentation_requirements="Add the rule to `docs/detection/rules.md`.",
    ),
    TaskDefinition(
        task_id="TASK-019",
        title="Detection pipeline runner: records to scored leads",
        priority="P0",
        area="detection",
        depends_on=("TASK-004", "TASK-009", "TASK-010"),
        objective=(
            "One entry point that runs every registered detector over a loaded "
            "scenario, scores the signals into `Lead`s, and persists them via the "
            "TASK-009 repositories.\n\n"
            "This is the step that turns detection from a library into a product "
            "stage: after it runs, the database holds leads the API can serve and "
            "the agent can investigate. It is on the critical path to the vertical "
            "slice."
        ),
        allowed_paths=("detection/pipeline.py", "scripts/demo/run_detection.py"),
        forbidden_paths=("detection/rules/**", "detection/graph/**", "frontend/**", "agent/**", "data/answer_keys/**"),
        acceptance_criteria=(
            "Running the pipeline on the demo scenario produces persisted, scored "
            "leads.",
            "A detector that raises is isolated: the pipeline records the failure "
            "and continues with the others, rather than losing the whole run.",
            "The run reports per-detector counts and elapsed time.",
            "Re-running is idempotent -- it does not duplicate leads for signals "
            "already recorded.",
            "Leads are ordered by score, so the top lead is the one the demo opens "
            "with.",
        ),
        tests_required="`tests/integration/` runs the pipeline over a loaded scenario and asserts leads land in the database; `tests/scenarios/` asserts the top leads match the answer key.",
        documentation_requirements="Update `detection/README.md` with how to run the pipeline.",
    ),
)


#: AGENT -- the bounded investigator, its tools, and what it produces.
_AGENT: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-020",
        title="Investigation state machine",
        priority="P0",
        area="agent",
        depends_on=("TASK-008", "TASK-009"),
        objective=(
            "Implement the investigation state described in "
            "`docs/investigation/protocol.md`: the object that tracks one "
            "investigation from a lead through the steps taken, the tools called, "
            "the evidence gathered and the conclusion reached.\n\n"
            "The agent loop (TASK-021) drives this; the API (TASK-037) serves it; "
            "the timeline UI (TASK-041) renders it. It is the shared spine of the "
            "investigation half of the product, so define it before the loop that "
            "mutates it."
        ),
        allowed_paths=("agent/runtime/state.py", "agent/runtime/__init__.py"),
        forbidden_paths=("database/**", "frontend/**", "detection/**", "domain/schemas/**"),
        acceptance_criteria=(
            "An investigation records every step in order, with the tool called, "
            "its arguments, and the result's provenance.",
            "State transitions are explicit and illegal transitions are refused.",
            "The state serializes to and from the TASK-008 `InvestigationStep` "
            "entities without loss.",
            "State can be rehydrated mid-investigation, so a crash does not lose the "
            "work already done.",
        ),
        tests_required="`tests/unit/` for transitions, ordering, and serialization round-trip.",
        documentation_requirements="Update `agent/runtime/README.md` with the state diagram.",
    ),
    TaskDefinition(
        task_id="TASK-021",
        title="Bounded agent loop with stopping conditions",
        priority="P0",
        area="agent",
        depends_on=("TASK-005", "TASK-020"),
        objective=(
            "Implement the bounded investigation loop from "
            "`docs/investigation/protocol.md`: given a lead, decide which tool to "
            "call next, call it, record the step, and decide whether to continue.\n\n"
            "Bounded is the load-bearing word (ADR-0002). The loop must stop on "
            "every one of: a step budget, a wall-clock budget, a token/cost budget, "
            "a confidence threshold reached, no new information from the last N "
            "steps, or a tool error it cannot route around. An agent that can loop "
            "forever on a paid API is the single most expensive bug available to us."
        ),
        allowed_paths=("agent/runtime/loop.py", "agent/runtime/stopping.py", "agent/policies/**", "agent/prompts/investigator.md"),
        forbidden_paths=("database/**", "frontend/**", "detection/**", "agent/runtime/state.py"),
        acceptance_criteria=(
            "Every stopping condition listed in the objective is implemented and "
            "independently tested.",
            "The loop cannot exceed its step budget under any input, including a "
            "model that keeps requesting tools.",
            "Every iteration appends a step to the TASK-020 state before the next "
            "call, so an interrupted run still shows what happened.",
            "A tool error is recorded and the loop decides explicitly whether to "
            "continue -- it never silently retries forever.",
            "The loop is testable without calling a real model (inject the model "
            "client).",
        ),
        tests_required=(
            "`tests/unit/` with a scripted fake model driving each stopping "
            "condition, including the adversarial 'model always asks for another "
            "tool' case."
        ),
        documentation_requirements="Document the budgets and their defaults in `agent/runtime/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-022",
        title="Gemini adapter with function calling",
        priority="P0",
        area="agent",
        depends_on=("TASK-005",),
        objective=(
            "Implement the Gemini client behind a narrow interface the agent loop "
            "depends on: send a prompt plus the TASK-005 tool schemas, get back "
            "either a tool call or a final answer.\n\n"
            "Route through `orchestrator/routing/` so spend lands in the usage "
            "ledger and a key switch is logged as a `ROUTING_EVENT` -- the budget is "
            "~USD 300 across four projects and untracked spend is how that "
            "disappears."
        ),
        allowed_paths=("agent/runtime/gemini.py", "agent/runtime/model.py"),
        forbidden_paths=("frontend/**", "detection/**", "database/**", "agent/runtime/loop.py"),
        acceptance_criteria=(
            "Tool schemas from TASK-005 are passed as function declarations without "
            "a second hand-maintained copy.",
            "Every call records usage (tokens, model, estimated cost) in the "
            "existing usage ledger.",
            "A rate-limit or transient error is retried with backoff a bounded "
            "number of times, then surfaces as a typed error.",
            "The model identifier is configurable; no model name is hard-coded in "
            "the loop.",
            "The adapter is unit-testable without network access.",
        ),
        tests_required="`tests/unit/` against a stubbed transport: tool-call parsing, final-answer parsing, retry/backoff, and ledger recording.",
        documentation_requirements="Update `agent/runtime/README.md` with configuration and the env vars required.",
    ),
    TaskDefinition(
        task_id="TASK-023",
        title="Structured agent outputs with schema validation",
        priority="P0",
        area="agent",
        depends_on=("TASK-022",),
        objective=(
            "Make every model output the system acts on a validated structure, not "
            "prose: tool calls, findings, confidence, and the final conclusion.\n\n"
            "A model returning malformed JSON is an expected condition, not an "
            "exception -- handle it with a bounded repair attempt and then a clean "
            "typed failure."
        ),
        allowed_paths=("agent/runtime/structured.py",),
        forbidden_paths=("frontend/**", "detection/**", "database/**", "agent/runtime/loop.py"),
        acceptance_criteria=(
            "Malformed output is retried a bounded number of times, then fails "
            "cleanly with the raw text preserved for debugging.",
            "A validated output can never contain a tool name that is not in the "
            "registry.",
            "Confidence values are constrained to a documented range.",
            "Validation failures are recorded on the investigation step, not "
            "swallowed.",
        ),
        tests_required="`tests/unit/` for valid output, malformed JSON, unknown tool name, and out-of-range confidence.",
        documentation_requirements="Document the output contract in `agent/runtime/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-024",
        title="Agent decision logging",
        priority="P0",
        area="agent",
        depends_on=("TASK-020",),
        objective=(
            "Record why the agent did what it did: for each step, the candidate "
            "actions considered, the one chosen, the stated reason, and the "
            "confidence.\n\n"
            "This is what makes the investigation auditable rather than magic, and "
            "it is what the live-agent-events UI (TASK-042) and the judge Q&A "
            "(TASK-027) both read. A forensic tool whose own reasoning is "
            "unauditable defeats its purpose."
        ),
        allowed_paths=("agent/runtime/decision_log.py",),
        forbidden_paths=("frontend/**", "detection/**", "database/**", "agent/runtime/loop.py"),
        acceptance_criteria=(
            "Every decision entry names the step, the action taken, the reason and "
            "the confidence.",
            "The log is append-only -- an entry is never rewritten after the fact.",
            "Entries are serializable for the event stream and the case file.",
            "Logging a decision cannot fail the investigation: a logging error is "
            "recorded, not raised into the loop.",
        ),
        tests_required="`tests/unit/` for append-only behaviour, serialization, and failure isolation.",
        documentation_requirements="Update `agent/runtime/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-025",
        title="Evidence accumulation and provenance chain",
        priority="P0",
        area="evidence",
        depends_on=("TASK-008", "TASK-005"),
        objective=(
            "Turn tool results into `Evidence`: collect what the investigation "
            "found, deduplicate it, rank it by strength, and keep every item's chain "
            "back to the source records.\n\n"
            "`docs/contracts/evidence.md` is the contract. The rule that matters: "
            "no evidence without provenance. An unsourced claim must be impossible "
            "to add, not merely discouraged."
        ),
        allowed_paths=("evidence/**",),
        forbidden_paths=("frontend/**", "detection/**", "database/**", "agent/runtime/**"),
        acceptance_criteria=(
            "Evidence cannot be created without source record ids.",
            "The same finding reached by two tools is deduplicated, keeping both "
            "provenance paths.",
            "Evidence is ranked by a documented strength measure.",
            "The full chain from a conclusion back to source records can be walked "
            "programmatically.",
            "Contradictory evidence is retained and marked, not silently dropped.",
        ),
        tests_required="`tests/unit/` for provenance enforcement, deduplication, ranking, and the contradiction case.",
        documentation_requirements="Update `evidence/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-026",
        title="Case file generation",
        priority="P0",
        area="agent",
        depends_on=("TASK-025",),
        objective=(
            "Generate the `Case` from a completed investigation: the narrative, the "
            "findings, the evidence with its provenance, the money trail, and a "
            "stated confidence with the reasoning behind it "
            "(`docs/contracts/case.md`).\n\n"
            "This is the product's actual output -- the artefact a human investigator "
            "would act on. Every claim in the narrative must be traceable to "
            "evidence; a narrative that reads well but cannot be sourced is the "
            "failure mode to design against."
        ),
        allowed_paths=("agent/case/**", "agent/prompts/case.md"),
        forbidden_paths=("frontend/**", "detection/**", "database/**", "evidence/**"),
        acceptance_criteria=(
            "Every claim in the generated narrative cites the evidence supporting it.",
            "The case states a confidence and the reasons for it, including what "
            "would change the conclusion.",
            "A case generated from an investigation that found nothing says so "
            "clearly -- it does not manufacture a narrative.",
            "The case serializes to the `Case` entity and is persisted.",
            "Generation is deterministic given the same investigation state and a "
            "fixed model response.",
        ),
        tests_required="`tests/unit/` with a fixed investigation state; `tests/scenarios/` asserts the case for the demo scenario names the entities in the answer key.",
        documentation_requirements="Update `agent/README.md` with the case-generation flow.",
    ),
    TaskDefinition(
        task_id="TASK-027",
        title="Judge Q&A over a completed case",
        priority="P1",
        area="agent",
        depends_on=("TASK-026",),
        objective=(
            "Answer free-form questions about a completed case, grounded strictly in "
            "the evidence and decision log -- 'why do you think this supplier is "
            "fraudulent', 'what would change your mind', 'how did you find this'.\n\n"
            "This is the demo's most exposed surface: it is answered live, in front "
            "of judges, on questions nobody scripted. Grounding is everything -- the "
            "correct answer to a question the evidence cannot support is to say so."
        ),
        allowed_paths=("agent/qa/**", "agent/prompts/qa.md"),
        forbidden_paths=("frontend/**", "detection/**", "database/**", "evidence/**"),
        acceptance_criteria=(
            "Every answer cites the evidence or decision-log entries it rests on.",
            "A question the case cannot answer gets an explicit 'the evidence does "
            "not show that', never an invented answer.",
            "Answers are bounded in length and latency, so the demo does not stall.",
            "The Q&A cannot reach the answer keys -- it sees only what the "
            "investigation produced.",
        ),
        tests_required="`tests/unit/` with a fixed case: an answerable question, an unanswerable one, and one whose premise is false.",
        documentation_requirements="Update `agent/README.md`.",
    ),
)


#: AGENT TOOLS -- each plugs into the TASK-005 registry, one file each.
_TOOLS: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-028",
        title="Agent tool: trace_outgoing_funds / trace_incoming_funds",
        priority="P0",
        area="agent",
        depends_on=("TASK-005", "TASK-012"),
        objective=(
            "Implement the fund-tracing tools from `docs/contracts/agent-tools.md` "
            "over the TASK-012 graph: from an account or entity, follow money out "
            "(or in) to a bounded depth, returning each hop with amount, date and "
            "the source record id.\n\n"
            "This is the tool the money-trail UI renders and the one the agent leans "
            "on hardest. Depth must be bounded and the result must be traceable."
        ),
        allowed_paths=("agent/tools/trace_funds.py",),
        forbidden_paths=("agent/tools/base.py", "agent/tools/registry.py", "frontend/**", "database/**", "detection/**"),
        acceptance_criteria=(
            "Trace depth is a bounded parameter with a documented maximum.",
            "Every hop carries the source record id, so the UI can link to the "
            "underlying document.",
            "A cycle in the flow terminates the trace rather than looping.",
            "The result conforms to the `ToolResult` contract, including "
            "`execution_time` and `source_ids`.",
            "An entity with no outgoing flow returns an empty result, not an error.",
        ),
        tests_required="`tests/unit/` on a hand-built graph: straight chain, branching, cycle, and empty cases.",
        documentation_requirements="Update `agent/tools/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-029",
        title="Agent tool: relationship and counterparty analysis",
        priority="P0",
        area="agent",
        depends_on=("TASK-005", "TASK-012"),
        objective=(
            "Implement the relationship tools: who does this entity transact with, "
            "which counterparties are shared with another entity, and which "
            "identity attributes (address, phone, bank account, legal "
            "representative) are shared across entities."
        ),
        allowed_paths=("agent/tools/relationships.py",),
        forbidden_paths=("agent/tools/base.py", "agent/tools/registry.py", "frontend/**", "database/**", "detection/**"),
        acceptance_criteria=(
            "Shared-attribute results name which attribute matched and its value's "
            "source record.",
            "Results are capped and the cap is reported in the result.",
            "The tool conforms to the `ToolResult` contract.",
            "An entity with no relationships returns an empty result, not an error.",
        ),
        tests_required="`tests/unit/` for each relationship type against a fixture.",
        documentation_requirements="Update `agent/tools/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-030",
        title="Agent tool: document and invoice inspection",
        priority="P0",
        area="agent",
        depends_on=("TASK-005",),
        objective=(
            "Implement the tools that let the agent read the underlying documents: "
            "fetch an invoice with its line items, fetch a payment with its "
            "complement, and compare two invoices field by field."
        ),
        allowed_paths=("agent/tools/documents.py",),
        forbidden_paths=("agent/tools/base.py", "agent/tools/registry.py", "frontend/**", "database/**", "detection/**"),
        acceptance_criteria=(
            "Comparison returns a field-level diff, not a prose summary -- the model "
            "should reason over the diff.",
            "A missing document returns an error result, not an exception.",
            "Results conform to the `ToolResult` contract with source ids.",
        ),
        tests_required="`tests/unit/` for fetch, compare-identical, compare-different, and missing-document.",
        documentation_requirements="Update `agent/tools/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-031",
        title="Agent tool: EFOS / 69-B status check",
        priority="P1",
        area="agent",
        depends_on=("TASK-005", "TASK-011"),
        objective=(
            "Expose the TASK-011 EFOS lookup as an agent tool: given an RFC, return "
            "the 69-B listing status, the date it applied, and the provenance of the "
            "snapshot the answer came from."
        ),
        allowed_paths=("agent/tools/efos.py",),
        forbidden_paths=("agent/tools/base.py", "agent/tools/registry.py", "frontend/**", "database/**", "detection/**"),
        acceptance_criteria=(
            "The result states the snapshot date, so a stale answer is visible as "
            "stale.",
            "An unlisted RFC returns 'not listed' as a normal result.",
            "Conforms to the `ToolResult` contract.",
        ),
        tests_required="`tests/unit/` for listed, unlisted, and malformed RFC.",
        documentation_requirements="Update `agent/tools/README.md`.",
    ),
)


#: INTEGRATION -- the backend API, one endpoint group per task.
_API: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-032",
        title="Backend API skeleton with route auto-discovery",
        priority="P0",
        area="backend",
        depends_on=("TASK-009",),
        objective=(
            "Stand up the FastAPI application implementing `docs/contracts/api.md`: "
            "app factory, dependency wiring to the TASK-009 repositories, the shared "
            "error contract, CORS for the frontend, and health/readiness endpoints.\n\n"
            "Critically, routers must be auto-discovered from `backend/api/routes/`. "
            "Each endpoint task (TASK-033..039) then adds exactly one file and "
            "touches nothing shared -- which is what lets four machines build "
            "endpoints in parallel without conflicting on a central registration "
            "file."
        ),
        allowed_paths=("backend/api/main.py", "backend/api/app.py", "backend/api/deps.py", "backend/api/errors.py", "backend/api/routes/__init__.py"),
        forbidden_paths=("frontend/**", "detection/**", "agent/**", "domain/schemas/**"),
        acceptance_criteria=(
            "Dropping a new module into `backend/api/routes/` registers its routes "
            "with no edit to any shared file.",
            "Errors follow one documented shape across every endpoint, including "
            "validation failures.",
            "Health and readiness are distinct: readiness fails when the database is "
            "unreachable.",
            "The app starts with no database present and reports unready, rather "
            "than crashing on import.",
            "OpenAPI output matches `docs/contracts/api.md`.",
        ),
        tests_required="`tests/integration/` for app startup, the error contract, health/readiness, and auto-discovery of a test router.",
        documentation_requirements="Update `backend/api/README.md` with how to add an endpoint.",
    ),
    TaskDefinition(
        task_id="TASK-033",
        title="API: GET /leads and GET /leads/{id}",
        priority="P0",
        area="backend",
        depends_on=("TASK-032", "TASK-019"),
        objective=(
            "Serve the scored leads produced by the TASK-019 pipeline: a filterable, "
            "paginated list ordered by score, and a single lead with its detector "
            "signals and their source records. This is what the dashboard opens with."
        ),
        allowed_paths=("backend/api/routes/leads.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "The list is paginated and ordered by score descending by default.",
            "Filtering by status and by detector type works and is documented.",
            "A single lead includes the signals and the source record ids behind it.",
            "An unknown lead id returns the documented 404 error shape.",
            "Response shapes match `docs/contracts/api.md`.",
        ),
        tests_required="`tests/integration/` against a seeded database: list, pagination, filters, single, and not-found.",
        documentation_requirements="Update `backend/api/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-034",
        title="API: GET /entities/{id} profile",
        priority="P1",
        area="backend",
        depends_on=("TASK-032",),
        objective=(
            "Serve an entity profile: identity fields, EFOS status where known, "
            "counterparty summary, invoice and payment totals, and the leads that "
            "reference it. The screen a user reaches by clicking any entity anywhere "
            "in the UI."
        ),
        allowed_paths=("backend/api/routes/entities.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Totals are computed in the query, not by loading every record into "
            "memory.",
            "An unknown entity id returns the documented 404 shape.",
            "Response shape matches `docs/contracts/api.md`.",
        ),
        tests_required="`tests/integration/` for a known entity, an entity with no activity, and not-found.",
        documentation_requirements="Update `backend/api/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-035",
        title="API: POST /investigations (start an investigation)",
        priority="P0",
        area="backend",
        depends_on=("TASK-032", "TASK-021"),
        objective=(
            "Start an investigation from a lead: create the investigation record, "
            "kick off the bounded agent loop, and return immediately with the "
            "investigation id so the UI can subscribe to its event stream.\n\n"
            "The request must not block for the whole investigation -- the demo "
            "watches it happen live."
        ),
        allowed_paths=("backend/api/routes/investigations_start.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "The endpoint returns before the investigation completes, with an id "
            "that is immediately queryable.",
            "Starting an investigation twice for the same lead is either rejected or "
            "returns the existing one -- documented either way, never two parallel "
            "runs on one lead.",
            "A failure to start is reported in the documented error shape, and "
            "leaves no half-created investigation.",
        ),
        tests_required="`tests/integration/` for start, duplicate start, and start against an unknown lead.",
        documentation_requirements="Update `backend/api/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-036",
        title="API: GET /cases/{id}",
        priority="P0",
        area="backend",
        depends_on=("TASK-032", "TASK-008"),
        objective=(
            "Serve the generated case file: narrative, findings, evidence with "
            "provenance, money trail, and confidence -- the artefact the demo ends on."
        ),
        allowed_paths=("backend/api/routes/cases.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Evidence in the response carries its source record ids, so the UI can "
            "link every claim.",
            "A case for an investigation that is still running returns a documented "
            "'not ready' response rather than a partial case.",
            "An unknown case id returns the documented 404 shape.",
        ),
        tests_required="`tests/integration/` for a complete case, an in-progress investigation, and not-found.",
        documentation_requirements="Update `backend/api/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-037",
        title="API: GET /investigations/{id} with steps and evidence",
        priority="P0",
        area="backend",
        depends_on=("TASK-032", "TASK-020"),
        objective=(
            "Serve one investigation's current state: status, the steps taken in "
            "order with the tool called and its result summary, the evidence "
            "gathered so far, and the decision log. Works for a running "
            "investigation as well as a finished one -- the timeline UI polls or "
            "streams this."
        ),
        allowed_paths=("backend/api/routes/investigations.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Steps come back in the order they were recorded.",
            "A running investigation returns its partial state without error.",
            "Response shape matches `docs/contracts/api.md` and the "
            "`investigation_step` schema.",
            "An unknown investigation id returns the documented 404 shape.",
        ),
        tests_required="`tests/integration/` for running, complete, and unknown investigations.",
        documentation_requirements="Update `backend/api/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-038",
        title="API: live investigation event stream (SSE)",
        priority="P0",
        area="backend",
        depends_on=("TASK-032", "TASK-024"),
        objective=(
            "Stream investigation events to the browser as they happen -- step "
            "started, tool called, evidence found, conclusion reached -- using "
            "Server-Sent Events.\n\n"
            "SSE over WebSocket deliberately: the stream is one-directional and SSE "
            "reconnects on its own. This is what makes the demo feel live rather "
            "than like a page that eventually updates."
        ),
        allowed_paths=("backend/api/routes/events.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "A client subscribing mid-investigation receives subsequent events "
            "without needing the earlier ones.",
            "The stream terminates cleanly when the investigation finishes.",
            "A disconnected client does not leak a subscription or block the "
            "investigation.",
            "Event payload shapes are documented and match what TASK-024 records.",
            "The stream survives an investigation that errors -- it emits a failure "
            "event rather than hanging.",
        ),
        tests_required="`tests/integration/` for subscribe, mid-stream subscribe, clean termination, and the error case.",
        documentation_requirements="Document the event types in `backend/api/README.md` and `docs/integration-guide.md`.",
    ),
    TaskDefinition(
        task_id="TASK-039",
        title="API: POST /cases/{id}/questions (judge Q&A)",
        priority="P1",
        area="backend",
        depends_on=("TASK-032", "TASK-027"),
        objective=(
            "Expose the TASK-027 Q&A over HTTP: a question about a completed case, "
            "answered with citations to the evidence it rests on."
        ),
        allowed_paths=("backend/api/routes/questions.py",),
        forbidden_paths=("backend/api/main.py", "frontend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Answers include citations the UI can link to.",
            "Question length is bounded and over-long questions are rejected "
            "cleanly.",
            "A question against an incomplete case returns the documented 'not "
            "ready' response.",
            "Latency is bounded so the demo does not stall on a slow model call.",
        ),
        tests_required="`tests/integration/` for a normal question, an over-long one, and an incomplete case.",
        documentation_requirements="Update `backend/api/README.md`.",
    ),
)


#: FRONTEND -- each screen owns its own route directory, so screens can be
#: built concurrently on different machines.
_FRONTEND: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-040",
        title="Frontend: leads dashboard wired to the real API",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-033"),
        objective=(
            "Replace the dashboard's mock with the real `/leads` endpoint: the "
            "ranked lead list, each lead's score and detector, and the action that "
            "starts an investigation. The demo's opening screen."
        ),
        allowed_paths=("frontend/app/dashboard/**", "frontend/components/dashboard/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Leads load from the API, ordered by score, with pagination.",
            "Loading, empty and error states are all handled visibly -- no blank "
            "screen on a failed fetch.",
            "Starting an investigation navigates to the investigation view.",
            "No mock fixture remains in the dashboard path.",
        ),
        tests_required="Component tests for the loaded, empty and error states against a stubbed client.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-041",
        title="Frontend: investigation timeline",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-037"),
        objective=(
            "Render an investigation as an ordered timeline: each step, the tool "
            "called, what it returned, and the evidence it produced -- the view that "
            "shows the investigation was reasoned, not guessed."
        ),
        allowed_paths=("frontend/app/investigation/**", "frontend/components/timeline/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Steps render in order with their tool, arguments and result summary.",
            "A running investigation renders its partial timeline and indicates it "
            "is still going.",
            "Each step links to the evidence and source records behind it.",
            "A long investigation stays readable -- the timeline does not require "
            "horizontal scrolling.",
        ),
        tests_required="Component tests for running, complete and empty investigations.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-042",
        title="Frontend: live agent events via SSE",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-038"),
        objective=(
            "Subscribe to the TASK-038 event stream and render the agent's work as "
            "it happens -- the single most persuasive thing the demo does. Watching "
            "the investigator reason in real time is what separates this from a "
            "report generator."
        ),
        allowed_paths=("frontend/components/live-events/**", "frontend/lib/sse.ts"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Events appear as they arrive, without a page refresh.",
            "A dropped connection reconnects automatically and does not duplicate "
            "already-rendered events.",
            "The stream closing on completion is shown as completion, not as an "
            "error.",
            "An investigation that errors shows the failure rather than spinning "
            "forever.",
        ),
        tests_required="Component tests against a stubbed event source: normal flow, reconnect, completion, and error.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-043",
        title="Frontend: entity relationship graph",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-034"),
        objective=(
            "Render the entity/account graph around an investigation with "
            "Cytoscape.js (the default in `ARCHITECTURE.md`): nodes for entities, "
            "edges for flows, with the suspicious subgraph highlighted and every "
            "node clickable through to its profile."
        ),
        allowed_paths=("frontend/app/graph/**", "frontend/components/graph/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "The demo-scale graph renders and stays interactive (document the node "
            "count it was tested at).",
            "The subgraph the investigation implicates is visually distinct from "
            "background entities.",
            "Clicking a node opens that entity's profile.",
            "A graph too large to render usefully is summarised or filtered rather "
            "than drawn as a hairball.",
        ),
        tests_required="Component tests for rendering a fixture graph, the highlight, and the oversized-graph path.",
        documentation_requirements="Update `frontend/README.md` with the library choice and why.",
    ),
    TaskDefinition(
        task_id="TASK-044",
        title="Frontend: money trail visualization",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-037"),
        objective=(
            "Render the traced money path from the TASK-028 tool results: each hop "
            "with amount, date and counterparty, showing where the money went and "
            "how much was retained at each step."
        ),
        allowed_paths=("frontend/app/money-trail/**", "frontend/components/money-trail/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Each hop shows amount, date, counterparty and a link to the source "
            "record.",
            "Amounts are formatted as currency with the correct locale.",
            "A trail that hits its depth bound says so, rather than implying the "
            "trail ended.",
            "An empty trail renders an explicit empty state.",
        ),
        tests_required="Component tests for a multi-hop trail, a depth-bounded trail, and an empty one.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-045",
        title="Frontend: evidence panel with provenance",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-037"),
        objective=(
            "Render the evidence an investigation gathered, each item showing its "
            "strength and linking back to the source records -- the panel that lets "
            "a judge check any claim rather than take it on trust."
        ),
        allowed_paths=("frontend/app/evidence/**", "frontend/components/evidence/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Every evidence item links to the records that support it.",
            "Items are ordered by strength.",
            "Contradictory evidence is shown as such, not hidden.",
            "An investigation with no evidence renders an explicit empty state.",
        ),
        tests_required="Component tests for ranked evidence, the contradiction case, and the empty state.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-046",
        title="Frontend: case file view",
        priority="P0",
        area="frontend",
        depends_on=("TASK-006", "TASK-036"),
        objective=(
            "Render the generated case: narrative with inline citations, findings, "
            "confidence and its reasoning, and the evidence behind each claim. The "
            "screen the demo closes on."
        ),
        allowed_paths=("frontend/app/case/**", "frontend/components/case/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "Every citation in the narrative is a working link to its evidence.",
            "Confidence is shown with the reasoning behind it, not as a bare number.",
            "A case that is not ready renders a clear in-progress state.",
            "The case is readable on a projector: type size and contrast are checked "
            "at presentation resolution.",
        ),
        tests_required="Component tests for a complete case, an in-progress one, and citation links.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
    TaskDefinition(
        task_id="TASK-047",
        title="Frontend: judge Q&A panel",
        priority="P1",
        area="frontend",
        depends_on=("TASK-006", "TASK-039"),
        objective=(
            "Ask questions about a case and render the grounded answer with its "
            "citations. Used live, in front of judges, on unscripted questions."
        ),
        allowed_paths=("frontend/app/qa/**", "frontend/components/qa/**"),
        forbidden_paths=("frontend/app/layout.tsx", "backend/**", "detection/**", "agent/**"),
        acceptance_criteria=(
            "The answer renders with citations linking to evidence.",
            "A pending answer shows progress, so a slow model call does not look "
            "like a hang.",
            "An 'evidence does not show that' answer is rendered as a legitimate "
            "answer, not an error.",
            "A failed request is recoverable without reloading the page.",
        ),
        tests_required="Component tests for answered, unanswerable, pending and failed states.",
        documentation_requirements="Update `frontend/README.md`.",
    ),
)


#: TESTING -- the suites that prove the slice works and keep it working.
_TESTING: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-048",
        title="Frontend/backend contract tests",
        priority="P1",
        area="backend",
        depends_on=("TASK-033", "TASK-037"),
        objective=(
            "Pin the API contract from both sides: assert the served OpenAPI matches "
            "`docs/contracts/api.md`, and that the frontend's mock fixtures match "
            "the same shapes.\n\n"
            "Without this, the mock and the real API drift and the integration fails "
            "at the worst possible moment -- during the demo."
        ),
        allowed_paths=("tests/contract/test_api_contract.py",),
        forbidden_paths=("backend/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "A breaking change to any documented endpoint shape fails this suite.",
            "The frontend mock fixtures are validated against the same schemas as "
            "the real responses.",
            "The suite runs without a database or a model key.",
        ),
        tests_required="This task is the tests. It must fail when a contract is broken -- demonstrate that in the PR.",
        documentation_requirements="Update `docs/testing.md` with the contract level.",
    ),
    TaskDefinition(
        task_id="TASK-049",
        title="End-to-end demo scenario: data to case file",
        priority="P0",
        area="backend",
        depends_on=("TASK-019", "TASK-026", "TASK-036"),
        objective=(
            "One scripted run that exercises the whole vertical slice: load a "
            "scenario, run detection, take the top lead, investigate it, generate the "
            "case, and assert the case names the entities in the answer key.\n\n"
            "This is the definition of 'the product works'. It is also the demo "
            "rehearsal -- if it passes, the demo path is real; if it is skipped, "
            "nobody actually knows."
        ),
        allowed_paths=("tests/e2e/**", "scripts/demo/run_demo.py"),
        forbidden_paths=("backend/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "The run goes from empty database to generated case with no manual step.",
            "The generated case names the entities the answer key marks as "
            "fraudulent.",
            "The run reports elapsed time per stage, so the demo's timing is known "
            "in advance.",
            "It can run against a recorded model response as well as a live one, so "
            "it is usable in CI without spending budget.",
            "A failure names the stage that failed, not just 'the demo broke'.",
        ),
        tests_required="This task is the test. Run it against at least two different scenarios.",
        documentation_requirements="Update `docs/demo/runbook.md` with the exact commands and expected timings.",
    ),
    TaskDefinition(
        task_id="TASK-050",
        title="Scenario regression suite",
        priority="P1",
        area="detection",
        depends_on=("TASK-019",),
        objective=(
            "Lock in detector quality: for every scenario, assert precision and "
            "recall against the answer key and fail the build when either regresses "
            "beyond a documented tolerance.\n\n"
            "Detectors get tuned under time pressure. This is what stops a tweak that "
            "fixes one scenario from quietly breaking two others."
        ),
        allowed_paths=("tests/scenarios/test_regression.py",),
        forbidden_paths=("detection/**", "backend/**", "frontend/**", "agent/**"),
        acceptance_criteria=(
            "Per-scenario, per-detector precision and recall are asserted against "
            "documented baselines.",
            "A regression names the detector and the scenario that regressed.",
            "Baselines live in one place and changing one is a visible diff.",
            "The suite runs without a model key.",
        ),
        tests_required="This task is the tests. Demonstrate a deliberate regression failing the suite.",
        documentation_requirements="Update `docs/testing.md` with the baselines and how to change one.",
    ),
    TaskDefinition(
        task_id="TASK-051",
        title="Hidden fraud scenario: blind end-to-end test",
        priority="P1",
        area="detection",
        depends_on=("TASK-049",),
        objective=(
            "Generate a fraud scenario whose answer key no one has seen and run the "
            "full pipeline against it blind.\n\n"
            "Every other test risks being tuned to its fixture. This is the only one "
            "that answers the question the judges will actually ask: does it find "
            "fraud it was not built against? Record the honest result whatever it is "
            "-- a documented miss is worth more than a tuned pass."
        ),
        allowed_paths=("tests/scenarios/test_blind.py", "data/answer_keys/blind/**"),
        forbidden_paths=("detection/**", "backend/**", "frontend/**", "agent/**"),
        acceptance_criteria=(
            "The scenario is generated from a seed not used by any other test.",
            "The pipeline runs against it with no scenario-specific tuning.",
            "The result -- found, partially found, or missed -- is recorded in "
            "`history/experiments/` with the numbers.",
            "A miss does not fail the build; it is reported. This test measures, it "
            "does not gate.",
        ),
        tests_required="This task is the test. Report the blind result in the PR body.",
        documentation_requirements="Record the outcome in `history/experiments/` and summarise it in `docs/testing.md`.",
    ),
)


#: INFRASTRUCTURE -- what makes the demo survivable.
_INFRA: tuple[TaskDefinition, ...] = (
    TaskDefinition(
        task_id="TASK-052",
        title="Deployment: one-command local stack",
        priority="P1",
        area="infra",
        objective=(
            "A single command that brings up database, backend and frontend together "
            "from a clean checkout, so any of the four machines -- and the demo "
            "machine -- runs an identical stack.\n\n"
            "Has no code dependencies: it can be built now, in parallel with "
            "everything else."
        ),
        allowed_paths=("deployment/**", "docker-compose.yml", "Makefile"),
        forbidden_paths=("backend/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "One command brings the stack up from a clean checkout.",
            "Services wait for their dependencies rather than racing and crashing on "
            "first start.",
            "Ports and env vars are documented in one place.",
            "Bringing the stack down and up again preserves the loaded demo data, or "
            "documents clearly that it does not.",
        ),
        tests_required="A smoke script that brings the stack up, hits health, and tears it down.",
        documentation_requirements="Document the commands in `docs/deployment.md`.",
    ),
    TaskDefinition(
        task_id="TASK-053",
        title="Environment validation preflight",
        priority="P1",
        area="infra",
        objective=(
            "One command that checks a machine is actually ready: required env vars "
            "present and non-empty, database reachable, model key valid, Python and "
            "Node versions supported.\n\n"
            "Run before the demo. Discovering a missing key in front of judges is a "
            "preventable failure."
        ),
        allowed_paths=("scripts/validate/**",),
        forbidden_paths=("backend/**", "frontend/**", "agent/**", "detection/**"),
        acceptance_criteria=(
            "Every check reports pass or fail with the exact remedy for a failure.",
            "A missing model key is reported without printing the value of any "
            "secret.",
            "The command exits non-zero when any required check fails.",
            "It runs in seconds and needs no arguments.",
        ),
        tests_required="`tests/unit/` for each check against a simulated broken environment.",
        documentation_requirements="Document the preflight in `docs/deployment.md` and `docs/demo/runbook.md`.",
    ),
    TaskDefinition(
        task_id="TASK-054",
        title="Fallback mode: demo survives a model outage",
        priority="P1",
        area="infra",
        depends_on=("TASK-022", "TASK-049"),
        objective=(
            "Let the demo run end to end with no live model call, by replaying "
            "recorded investigation responses for the demo scenario.\n\n"
            "The deterministic half of the product -- detection, leads, graph, money "
            "trail -- does not need a model at all. Fallback mode must keep that "
            "fully live and replay only the agent's narration, so a provider outage "
            "costs polish rather than the demo."
        ),
        allowed_paths=("agent/runtime/fallback.py", "data/recorded/**"),
        forbidden_paths=("frontend/**", "detection/**", "backend/**", "agent/runtime/loop.py"),
        acceptance_criteria=(
            "The full demo path runs with the model provider unreachable.",
            "Fallback mode is visibly indicated in the UI -- it is never presented "
            "as a live investigation.",
            "Switching to fallback is one documented flag, usable under pressure.",
            "Deterministic detection, graph and money trail remain fully live in "
            "fallback mode.",
        ),
        tests_required="`tests/e2e/` runs the demo path with the provider stubbed unreachable.",
        documentation_requirements="Document the flag and what it changes in `docs/demo/runbook.md`.",
    ),
    TaskDefinition(
        task_id="TASK-055",
        title="Model API failure handling and budget guard",
        priority="P1",
        area="agent",
        depends_on=("TASK-022",),
        objective=(
            "Handle the ways a model provider fails -- rate limits, timeouts, "
            "malformed responses, quota exhaustion -- with bounded retry, provider "
            "rotation through the existing `orchestrator/routing/` pool, and a hard "
            "budget stop.\n\n"
            "The budget is ~USD 300 across four projects. A runaway loop can spend it "
            "in an afternoon, so the guard must be a hard stop, not a warning."
        ),
        allowed_paths=("agent/runtime/resilience.py",),
        forbidden_paths=("frontend/**", "detection/**", "backend/**", "agent/runtime/loop.py"),
        acceptance_criteria=(
            "Each failure mode has a distinct, tested behaviour -- no bare "
            "catch-all.",
            "Retries are bounded with backoff and never unbounded.",
            "Exhausting one provider's quota rotates to the next and logs a "
            "`ROUTING_EVENT`.",
            "Reaching the budget ceiling stops further calls rather than warning and "
            "continuing.",
            "Every failure and rotation lands in the usage ledger.",
        ),
        tests_required="`tests/unit/` per failure mode against a stubbed transport, including the budget-ceiling stop.",
        documentation_requirements="Update `agent/runtime/README.md` and `orchestrator/policies/provider-pool.yaml` notes.",
    ),
)


BACKLOG = _SPINE + _DOMAIN + _DATA + _DETECTION + _AGENT + _TOOLS + _API + _FRONTEND + _TESTING + _INFRA
