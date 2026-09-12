# AI development worker — setup and operation

How to get `worker start` running on a new machine, and what to do when
it stops. Referenced by `CONTRIBUTING.md` §1 and `orchestrator/README.md`.

> **What this worker is.** It builds *this repository*: it claims a task
> from the GitHub queue, writes code for it on an isolated branch, runs
> the tests, records a handoff, and opens a pull request. It is not the
> forensic agent, it never touches financial data, and it never merges
> anything (`CONTRIBUTING.md` §7).

---

## 1. Install

Requirements:

| Requirement | Why | Check |
|---|---|---|
| Python 3.11+ | the worker itself (standard library only) | `python3 --version` |
| git | branches, commits, pushes | `git --version` |
| The Claude Code CLI | the AI that writes the code | `claude --version` |
| A GitHub token | the task queue and claim protocol | see §3 |

```bash
git clone https://github.com/apache-61/truelock.git
cd truelock
pip install -r requirements-dev.txt        # pytest, for the validation gates
```

The worker imports nothing outside the standard library, so there is no
build step and no virtualenv requirement. `requirements-dev.txt` is for
the *tests it runs*, not for the worker.

**Use a dedicated clone.** The worker refuses to start on a dirty tree,
and it checks out a new branch per task. Sharing a clone with your own
editing session will interrupt one or the other.

---

## 2. WORKER_ID

Every machine gets its own stable identity, set once:

```bash
export WORKER_ID="WORKER-01"        # WORKER-01 .. WORKER-04, or a slug
```

This is what the claim protocol records as the owner of a task. It must
**not** be a GitHub username: four workstations can push through one
token, so the account name cannot distinguish them
(`CONTRIBUTING.md` §1).

Valid: `WORKER-01`, `WORKER-04`, `laptop-ana`, `ci_runner_2`
Invalid: `w`, `worker 01`, `worker/01`, anything under 3 characters.

Assign one ID per machine and never reuse another machine's. Two workers
sharing an ID is not a race the protocol can detect.

---

## 3. GitHub authentication

The worker needs a repo-scoped token with permission to read issues,
comment on them, apply labels, push branches, and open pull requests.

```bash
export GITHUB_TOKEN="ghp_..."       # or a fine-grained token
export GITHUB_OWNER="apache-61"
export GITHUB_REPO="truelock"
```

A fine-grained personal access token needs, on this repository:

- **Contents:** read and write (push branches)
- **Issues:** read and write (claims, labels, status comments)
- **Pull requests:** read and write (open the PR)
- **Metadata:** read

Nothing else. The worker never modifies secrets, permissions, branch
protection, or repository settings, and refuses commands that would
(`orchestrator/workers/safety.py`).

Persist these in `.env` at the repository root instead of your shell
profile if you prefer — `.env` is gitignored and `.env.example` lists
every key:

```bash
cp .env.example .env && $EDITOR .env
```

---

## 4. Claude authentication

The worker shells out to the Claude Code CLI, so the CLI must be
installed and authenticated once per machine:

```bash
claude          # follow the login prompt, then exit with /exit
claude --version
```

After that the worker invokes it non-interactively. Tune it with:

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDE_CLI_BIN` | `claude` | binary to invoke |
| `CLAUDE_CLI_EXTRA_ARGS` | *(none)* | extra CLI arguments, shell-split |
| `WORKER_MODEL` | CLI default | value for `--model` |
| `WORKER_AI_TIMEOUT` | `3600` | seconds before a task is abandoned |

---

## 5. Check the machine

```bash
python scripts/orchestration/worker.py doctor
```

It verifies the repository, the worker ID, the GitHub token (by making a
real API call), the Claude CLI, and that the tree is clean — and prints
what to do about anything missing.

To type `worker` instead of the full path:

```bash
export PATH="$PWD/scripts/orchestration:$PATH"
worker doctor
```

Add that line to your shell profile to make it permanent. Every example
below uses the short form.

---

## 6. Run it

**Always rehearse first.** A dry run reads the real queue, resolves a
real task, builds the real context pack, and runs the whole loop with a
mock AI — writing nothing to GitHub, git, or disk:

```bash
worker start --once --dry-run
```

It prints the writes a live run *would* have made. Read that list before
going live.

Then, for one task:

```bash
worker start --once
```

Or keep going until a stop condition:

```bash
worker start --continuous --max-tasks 5 --max-runtime 90
```

### Commands

| Command | What it does |
|---|---|
| `worker start --once` | claim and execute exactly one task (the default) |
| `worker start --continuous` | keep going until a stop condition is hit |
| `worker start --dry-run` | rehearse; change nothing, call no paid API |
| `worker start --task 4` | attempt only issue #4, if it is eligible |
| `worker status` | the queue as this worker sees it, with eligibility |
| `worker doctor` | check this machine's setup |

### Safety limits

| Flag | Effect |
|---|---|
| `--max-tasks N` | stop after N tasks |
| `--max-runtime MINUTES` | stop once the run has lasted this long |
| `--max-idle MINUTES` | stop after this long with nothing eligible |
| `--max-failure-streak N` | stop after N consecutive failures (default 3) |
| `--once` | exactly one task (the default; `--continuous` opts out) |
| `--dry-run` | no claim, no branch, no commit, no push, no PR |
| `--stop-on-blocker` | in `--continuous`, stop on the first BLOCKED |
| `--allow-auto-merge` | see §9 — almost always leave this off |

### Running four machines continuously

This is the mode the team runs during a build (ADR-0006). On each
machine, with its own `WORKER_ID`:

```bash
worker start --continuous --max-runtime 480
```

Each machine then loops: propagate merges → claim the next eligible task
→ execute → open a PR → repeat. Four of them stay out of each other's way
because the claim protocol (ADR-0003) resolves races and the backlog
guarantees that two concurrently-claimable tasks never write the same
paths (`orchestrator/task_queue/backlog.py`).

Three behaviours only apply in `--continuous`:

**It closes tasks whose PR a human merged.** Before each selection the
worker checks the PR for tasks it has already taken somewhere. Merged →
it labels the issue `status:done` and closes it, which is what makes
every task depending on it eligible. Closed unmerged → it releases the
claim and returns the task to the queue. It still never merges anything
(ADR-0005); it records a decision a human already made.

**It works through blockers.** A task ending BLOCKED or needing human
authorization no longer stops the machine — the issue carries the
explanation and the worker moves to the next task. Use `--once` or
`--stop-on-blocker` if you want it to stop and wait for you.

**It waits instead of exiting when the queue is dry.** Most tasks here
unlock only when somebody merges a PR, so an idle worker re-reads the
queue every `WORKER_POLL_SECONDS` (default 120, jittered so four machines
do not wake together and race for the same task). Bound it with
`--max-idle` if you want it to give up.

### What a live run looks like

The AI step is the slow one. A real task takes minutes, and the budget is
`WORKER_AI_TIMEOUT` (default 60m). The CLI is captured rather than
streamed, so its own output arrives only when it finishes — the worker
therefore says so before it starts, and prints elapsed time while it
waits:

```
ROUTING_EVENT from=none to=claude-code-cli reason=TASK-002:feature:tier1-2-development
running claude_code on TASK-002 — this is the slow step and prints nothing
until it finishes (budget 60m). Progress every 30s:
  ... still working — 0m30s elapsed
  ... still working — 1m00s elapsed
```

**A worker sitting on `... still working` is fine.** It is not hung. The
run only stops on its own at the budget, and every other step prints as
it happens.

### Interrupting a run

Ctrl+C is safe. The worker releases its claim, returns the task to
`status:ready`, and notes what happened on the issue, so another machine
can pick it up immediately rather than waiting out the three-hour
staleness window.

What it does *not* do is undo work already written: a task branch may
remain in your clone. Nothing is ever merged. If you interrupt and then
want to retry, make sure the tree is clean first (`git status`) — the
worker refuses to start a task on top of uncommitted changes.

### If a machine dies mid-task

Its claim would otherwise hold the task forever. Another worker takes
over once the issue has been silent for `WORKER_CLAIM_STALE_MINUTES`
(default 180 — three times the longest a single task may run). The
takeover posts a `RELEASE` on the issue naming both workers.

**If you see that comment and the named worker is still alive, stop it.**
Two workers on one task is exactly what the claim protocol exists to
prevent, and the only way this happens is a machine that went silent for
three hours and then resumed.

### Why a continuous run stopped

It always says. The reasons: no eligible task and `--max-idle` reached; a
limit (`--max-tasks`, `--max-runtime`); three consecutive failures —
unrelated tasks failing in a row usually means the machine is
misconfigured rather than the tasks being bad, so it stops for a human;
or, with `--once`/`--stop-on-blocker`, a BLOCKED or authorization
outcome. It never runs unbounded without you asking.

---

## 7. What one task actually does

```
 1. identify the worker        WORKER_ID, repo, token
 2. query GitHub               open issues (the source of truth, ADR-0003)
 3. find READY tasks           status:ready label, or the issue body
 4. order by priority          P0 → P3, then issue number
 5. check dependencies         every depends_on must be MERGED/VERIFIED
 6. CLAIM                      post claim_id + worker_id + timestamp
 7. VERIFY                     re-read; earliest live claim wins
 8. create branch              feature/TASK-###-slug off main
 9. build context              the task + only the docs it needs
10. run Claude Code            inside the allowed paths
11. enforce scope, validate    formatter → lint → types → unit → integration
12. write the handoff          task-result.json
13. write history              history/ai-activity/ + timeline
14. push and open a PR         never merged
15. update the task            labels and a status comment on the issue
16. next task                  or stop, per the limits above
```

If it loses the claim at step 7 it stops immediately and writes no code.

---

## 8. Task requirements

A task is executed only when **all** of these hold:

- status is READY and the task is authorized;
- every `depends_on` task is MERGED or VERIFIED (closed, or
  `status:done`);
- it is not BLOCKED;
- no other worker holds a live claim;
- `execution_mode` is `auto`.

A task marked `execution:human` (or `human_authorization: yes`) makes the
worker **stop before writing any code** and post a proposal on the issue
instead (`CONTRIBUTING.md` §5).

### Scope

Each task declares `allowed_paths` and `forbidden_paths`. The worker
checks every changed file against them. If the work needs a path it was
not granted, it **stops, marks the task BLOCKED, and explains what is
missing** — it never widens its own scope. To unblock, a human either
extends `allowed_paths` or creates a task that owns those paths and adds
it to `depends_on`.

A task that declares no `allowed_paths` can change nothing at all. That
is deliberate: a drafting omission must not become an unbounded diff.

---

## 9. Merging

The worker never merges. Every run ends at an open pull request, and a
human decides (`CONTRIBUTING.md` §5, `tasks/ready/TASK-007-*.md`).

`--allow-auto-merge` exists for simple, pre-authorized tasks, and needs
**three** independent conditions before it will merge anything:

1. a human passes `--allow-auto-merge` on the command line;
2. the task issue carries the `execution:auto-merge-approved` label,
   applied by a human beforehand;
3. the change touches none of: architecture, contracts, JSON schemas,
   security policy, database migrations, CI or repository governance —
   and the task type is not security, decision, experiment, or research.

Any one of those missing means no merge. Leave the flag off unless the
team has explicitly agreed otherwise for a specific task.

---

## 10. What it produces

| Artifact | Where |
|---|---|
| The code | a `feature/`, `fix/`, `research/` or `experiment/` branch |
| The handoff | `.state/task-result-<run-id>.json` and the PR body |
| The history entry | `history/ai-activity/<date>-<task>-<run-id>.md` |
| One timeline line | `history/timeline.md` |
| The usage ledger | `.state/usage.jsonl` |
| Task state | labels and a status comment on the GitHub issue |

`.state/` is gitignored and is never a source of truth
(`orchestrator/state/README.md`).

---

## 11. Troubleshooting

**`WORKER_ID is not set`**
Set it (§2). There is no default on purpose — a guessed identity would
make claims unattributable.

**`GITHUB_TOKEN is required for live runs`**
Set a token (§3), or add `--dry-run`.

**`the Claude Code CLI ('claude') is not on PATH`**
Install and authenticate it (§4), or run with `--adapter mock` to
exercise the loop without an AI.

**`working tree is dirty; refusing to start a task`**
Commit, stash, or clean. Starting on top of uncommitted work would sweep
it into the task's PR.

**`No eligible READY task`**
`worker status` prints why each task was skipped — usually an unmet
dependency or another worker's claim.

**`LOST claim on TASK-xxx`**
Working as designed: another worker got there first. The worker withdrew
its claim and stopped. Run it again to pick up the next task.

**`note: no open issue carries the 'status:ready' label`**
The repository's labels have not been created yet
(`PROJECT_STATE.md` → "Blocked"). The worker falls back to reading task
state from issue bodies, which works. To remove the notice, someone with
`gh` repo-admin rights runs `scripts/setup/create_labels.sh` once.

**`note: could not add label 'status:claimed'`**
Same cause, same fix. Label updates are advisory; the claim comments are
the authoritative record, so the run continues.

**`SCOPE VIOLATION — stopping without a PR`**
The AI tried to change a path the task does not own. The branch is pushed
for inspection and the issue explains what was out of scope. Widen
`allowed_paths` deliberately, or split the work into its own task.

**`NOT VERIFIED (nothing ran)`**
Every validation gate was skipped — usually pytest is not installed.
Install `requirements-dev.txt`. The PR is opened as a draft, because a
change nothing ran against must not look review-ready.

**The PR says `[VALIDATION FAILED]`**
The tests really failed. The failure output is in the PR body and the
history entry. Fix it on the branch; the worker does not retry
automatically, and it never disables a test to get to green.

**A task is stuck in `status:claimed` after a crash**
Release it so another worker can take it:

```bash
python scripts/orchestration/task_cli.py release --issue <number>
```

---

## 12. Verifying a change to the worker

Offline coverage runs in seconds and needs no credentials:

```bash
pytest -q tests/unit tests/contract
```

After changing the adapter — or after the Claude Code CLI is upgraded —
also run the live test, which drives the whole loop against the real CLI
in a throwaway repository:

```bash
WORKER_LIVE_AI_TEST=1 pytest -q tests/integration/test_worker_live_claude.py
```

It is skipped by default and in CI (`docs/testing.md`). What only it can
prove is that the CLI is still invoked correctly, that its JSON envelope
still parses into a valid result, and that real token usage still reaches
the ledger.

## 13. Limits of this MVP

- **One provider.** Only the Claude Code CLI is wired up. The routing
  layer, `ROUTING_EVENT` logging and the usage ledger are real and
  tested, so adding Gemini is a registration rather than a rewrite — but
  multi-provider routing is deliberately not built yet.
- **Token accounting is as honest as the CLI is.** Costs are recorded
  when the CLI reports them and left null otherwise. The worker never
  estimates a number for a budget ledger. The ledger names the model that
  actually served the turn, which is not always the one requested.
- **The AI may be unable to run commands.** If the CLI denies its
  permission requests, the worker records the denials, forces human
  review, and still runs the validation gates itself — so a run where the
  AI could not execute tests never passes as if it had.
- **The claim protocol detects races, it does not prevent them.** That is
  the accepted trade-off in ADR-0003; two claim comments on one issue are
  immediately visible if it ever happens.
- **CI is not awaited.** The worker opens the PR and stops; it does not
  poll for the CI result. Auto-merge, when explicitly enabled, therefore
  still requires a human to confirm CI is green.
