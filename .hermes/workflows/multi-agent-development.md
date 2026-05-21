# Multi-Agent Development Workflow

This workflow describes how to develop the personal budget platform with Hermes subagents first, and with external agents such as Claude Code later.

## Goals

- Keep work split into small, reviewable slices.
- Let multiple agents work in parallel without editing the same files.
- Require implementation + spec review + quality review before integration.
- Make every handoff reproducible with exact commands and changed files.

## Default workflow for a feature

### 1. Plan

Planner reads:

- `AGENTS.md`
- current code and tests
- the user request
- any existing plan in `.hermes/plans/`

Planner writes a plan with:

- feature goal
- assumptions
- exact files to create/modify
- task list in dependency order
- TDD steps for behavior changes
- verification commands
- rollback/migration notes if needed

Plans should be saved as:

```text
.hermes/plans/YYYY-MM-DD-short-feature-name.md
```

### 2. Assign tasks

Break work into independent tasks. Use this rule:

- Same files or same migration chain: sequential work.
- Different bounded areas: parallel work in separate worktrees.

Examples:

- Backend accounts domain: one implementer.
- Frontend skeleton: another implementer.
- Review of migration/test quality: reviewer after implementation.

### 3. Implement task

Implementer must:

1. Read `AGENTS.md` and the task plan.
2. Check `git status` before editing.
3. Write failing tests first for new behavior.
4. Implement the minimum necessary change.
5. Run narrow checks.
6. Produce a handoff.

Expected handoff:

```markdown
## Implementer handoff

**Goal:** ...
**Changed files:**
- `path/to/file`

**Commands run:**
- `command` — PASS/FAIL

**Result:** ...
**Risks/open questions:** ...
**Next step:** ...
```

### 4. Spec review

Spec Reviewer checks:

- Does the change satisfy the requested behavior?
- Did it avoid unapproved product assumptions?
- Are important edge cases covered?
- Did it stay within scope?

Reviewer returns one of:

- `APPROVED`
- `CHANGES_REQUESTED`

### 5. Quality review

Quality Reviewer checks:

- code quality and maintainability
- migrations and downgrade paths
- tests and fixtures
- async correctness
- security and secrets
- money/currency/date precision
- frontend type safety when applicable

Reviewer returns one of:

- `APPROVED`
- `CHANGES_REQUESTED`

### 6. Integrate

Integrator must:

1. Apply/merge accepted changes.
2. Resolve conflicts deliberately.
3. Run full relevant checks.
4. Inspect `git diff` before commit.
5. Commit with a clear message.
6. Prepare PR or final handoff.

Backend full checks:

```bash
cd backend
uv run ruff check .
uv run pytest -q
uv run alembic downgrade base
uv run alembic upgrade head
```

Frontend full checks once frontend exists:

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

## Worktree workflow

Use git worktrees for parallel agents when two tasks can proceed independently.

Recommended layout:

```text
/home/primalex/projects/personal-budget-platform/                  # main checkout
/home/primalex/projects/personal-budget-platform-worktrees/
  backend-accounts/
  frontend-skeleton/
  review/
```

Example commands:

```bash
mkdir -p /home/primalex/projects/personal-budget-platform-worktrees
cd /home/primalex/projects/personal-budget-platform
git fetch origin
git worktree add ../personal-budget-platform-worktrees/backend-accounts -b feat/backend-accounts
git worktree add ../personal-budget-platform-worktrees/frontend-skeleton -b feat/frontend-skeleton
```

Rules:

- One agent per worktree.
- One branch per worktree.
- Do not let two agents edit the same files in parallel.
- Integrate through commits/PRs, not by copying files manually unless explicitly needed.

## Claude Code workflow

Claude Code should follow `AGENTS.md`. Add a root `CLAUDE.md` that points Claude to these rules.

Preferred one-shot command for bounded tasks:

```bash
claude -p "Read AGENTS.md. Implement the task described in .hermes/plans/<plan>.md. Stop after the task, run relevant checks, and summarize changed files." \
  --allowedTools "Read,Edit,Write,Bash" \
  --max-turns 10
```

For read-only review tasks:

```bash
git diff main...HEAD | claude -p "Read AGENTS.md, then review this diff for bugs, missing tests, unsafe migrations, security issues, and domain mistakes. Return findings only; do not edit files." \
  --allowedTools "Read" \
  --max-turns 1
```

For interactive sessions, use tmux and clean up after completion:

```bash
tmux new-session -d -s claude-budget -x 140 -y 40
tmux send-keys -t claude-budget 'cd /home/primalex/projects/personal-budget-platform && claude' Enter
tmux capture-pane -t claude-budget -p -S -50
tmux kill-session -t claude-budget
```

## Agent assignment template

```markdown
You are the [Planner/Implementer/Spec Reviewer/Quality Reviewer/Integrator] for `personal-budget-platform`.

Read first:
- `AGENTS.md`
- `.hermes/workflows/multi-agent-development.md`
- `[specific plan file]`

Task:
[exact task]

Constraints:
- Stay within scope.
- Do not touch unrelated files.
- Use TDD for behavior changes.
- Run relevant checks.
- Return the standard handoff format.
```

## Stop-and-ask triggers

Agents must stop and ask the human when:

- a product decision changes user-visible behavior;
- financial/accounting semantics are ambiguous;
- a migration may destroy or rewrite data;
- a task requires secrets, credentials, or real personal data;
- a destructive command is needed;
- frontend UX decisions materially affect navigation, flows, or terminology.

## Current recommended next phases

1. Finish and merge database foundation.
2. Add backend accounts domain and migrations.
3. Add transactions domain and import foundation.
4. Create frontend skeleton with React + TypeScript + Vite.
5. Connect frontend to backend health/config/API client.
