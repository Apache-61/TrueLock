# orchestrator/task_queue/

**Purpose:** the backlog *definition* — what work exists, in what order,
with what scope. Not a state store.

**What is here:** `backlog.py`, the 55-task implementation backlog as
data, plus the guards on it.

GitHub Issues remain the single source of truth for task **state and
claims** (`history/decisions/ADR-0003-task-coordination.md`). This module
does not compete with that: it defines what a task *is*, and
`scripts/orchestration/seed_backlog.py` renders it into the two places a
task is read from —

```
orchestrator/task_queue/backlog.py     (definition, one source)
            |
            +--> tasks/{ready,...}/TASK-###-*.md   human-readable mirror
            +--> GitHub issues                     the queue workers claim
```

Both renders come from one `render_markdown()`, so a human reading
`tasks/ready/` and a worker parsing the issue body are reading the same
text. `tests/unit/test_backlog.py` asserts that what the seeder renders
is what `orchestrator/workers/tasks.py::parse_issue` reads — if that
dialect drifts, a worker silently sees a task with no `allowed_paths`,
which means no scope enforcement at all.

## The two guards

`validate()` refuses to seed a backlog that would break the team:

1. **Deadlock.** An unknown dependency, a self-dependency, or a cycle.
   A cycle makes every worker report "no eligible task" with no
   explanation, on all four machines at once — each task waiting on
   something that will never be satisfied. It looks exactly like an
   empty queue.

2. **Collision.** Two tasks with no dependency between them that declare
   overlapping `allowed_paths`. Those can be claimed at the same moment
   by different machines, and no claim protocol prevents the merge
   conflict that follows — the claim protocol stops two workers taking
   one *task*, not two tasks touching one *file*. This is what drove the
   per-file scoping of the detectors, the API endpoints and the frontend
   screens: each owns its own file or route directory.

## Changing the backlog

Edit `backlog.py`, then:

```bash
python scripts/orchestration/seed_backlog.py --dry-run   # what would change
python scripts/orchestration/seed_backlog.py             # apply
```

It is idempotent and updates issues in place. It never opens a second
issue for a task that already has one — that would split the task's claim
history, and the claim protocol only holds while there is exactly one
comment thread per task. If it finds a duplicate it reports it and
refuses to guess.

Do not hand-edit `tasks/BACKLOG.md` or the files under `tasks/ready/`:
they are generated, and the next seeder run overwrites them.

**Depends on:** `tasks/README.md`, `orchestrator/workers/tasks.py`.
