# Agent Rules — Personal Budget Platform

This repository is a personal budget platform. These rules are the shared contract for Hermes subagents, Claude Code, Codex/OpenCode, and any other coding agent working in this repo.

## Project shape

- Repository: `personal-budget-platform`
- Current backend stack: FastAPI, SQLAlchemy asyncio, Alembic, PostgreSQL, Pydantic Settings, pytest, ruff, uv.
- Current backend path: `backend/`
- Current infra path: `infra/`
- Planned frontend stack: React + TypeScript + Vite, under `frontend/` when created.
- Primary product goal: personal/family/trip budget management with accounts, transactions, categories, currencies, exchange rates, budgets, debts, goals, rewards, imports, and analytics over time.

## Non-negotiable principles

1. **Small, reviewable changes.** Prefer narrow PRs and frequent commits over large mixed changes.
2. **TDD for behavior.** For new behavior, write or update tests first, see them fail for the intended reason, then implement the minimum code.
3. **No secrets.** Never commit real credentials, tokens, `.env`, database dumps, or personal financial data.
4. **Backward-compatible migrations.** Every schema change must include an Alembic migration and a downgrade path unless explicitly documented otherwise.
5. **Domain precision.** Money, currency, and dates must be modeled deliberately. Avoid floats for monetary values.
6. **No silent scope creep.** Implement only the requested slice. If a product decision materially affects behavior, stop and ask the human.
7. **Keep generated artifacts out of git.** Do not commit caches, virtualenvs, build outputs, coverage files, or local database files.

## Git workflow

- Work from a clean branch/worktree whenever possible.
- Use descriptive branch names:
  - `feat/backend-accounts`
  - `feat/frontend-skeleton`
  - `feat/import-csv`
  - `fix/database-foundation-review`
- Do not rewrite public history unless the human explicitly asks.
- Before committing, run relevant checks and include the command output summary in the handoff.
- Commit messages should be concise conventional-style where practical:
  - `feat: add account model`
  - `test: cover transaction validation`
  - `docs: add multi-agent workflow`
  - `fix: repair alembic metadata loading`

## Backend rules

- Use Python 3.12+ compatible code.
- Keep application code under `backend/app/` and tests under `backend/tests/`.
- Use SQLAlchemy 2.x typed declarative style for ORM models.
- Use async DB access for runtime code.
- Put shared DB metadata and base model logic in `backend/app/db/`.
- Add/update Alembic migrations under `backend/alembic/versions/` for schema changes.
- Keep seed/reference data explicit and idempotent.
- Use Pydantic/Pydantic Settings for configuration; read config from environment, not hardcoded secrets.
- Prefer service/repository boundaries once business logic grows; keep FastAPI route handlers thin.

## Backend commands

Run from `backend/` unless stated otherwise:

```bash
uv sync
uv run ruff check .
uv run pytest -q
uv run alembic downgrade base
uv run alembic upgrade head
```

When adding migrations, verify both upgrade and downgrade paths. If a local PostgreSQL container is needed, use the compose file from the repo root:

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

## Frontend rules

The frontend is planned but may not exist yet. When created:

- Path: `frontend/`
- Stack: React + TypeScript + Vite.
- Use strict TypeScript.
- Prefer feature/page-based structure with shared API/client utilities.
- Do not duplicate backend domain rules in UI code unless needed for user experience; backend remains source of truth.
- Keep generated API clients reproducible if OpenAPI generation is introduced.
- Add tests for non-trivial UI behavior and data transformations.

Expected commands once frontend exists:

```bash
npm install
npm run lint
npm run typecheck
npm test
npm run build
```

## Product/domain guardrails

- Monetary amounts: use `Decimal`/database numeric types, never binary floats.
- Currency codes: use ISO-like uppercase 3-letter codes unless a requirement says otherwise.
- Dates/times: store timezone-aware timestamps where time matters; use dates for date-only financial events.
- Exchange rates: preserve rate source and effective date/time where available.
- Imports: preserve enough metadata to trace imported rows and detect duplicates.
- Multi-user/workspace features must enforce ownership and access rules; never expose another user's data by default.

## Multi-agent roles

Use these roles when splitting work:

### Planner

- Reads requirements and current code.
- Produces a bite-sized plan with exact file paths, tests, commands, and acceptance criteria.
- Does not implement unless explicitly asked.

### Implementer

- Implements one small task at a time.
- Uses TDD for new behavior.
- Runs the narrowest relevant checks before handoff.
- Reports changed files, tests run, and known risks.

### Spec Reviewer

- Checks whether implementation matches the requested behavior and plan.
- Flags missing acceptance criteria, wrong domain assumptions, and scope creep.
- Does not focus on style unless it affects correctness.

### Quality Reviewer

- Checks maintainability, security, migrations, typing, test quality, and edge cases.
- Looks for regressions, flaky tests, secrets, and unsafe commands.
- Recommends concrete fixes.

### Integrator

- Combines accepted work.
- Resolves conflicts.
- Runs full relevant checks.
- Prepares final commit/PR summary.

## Agent handoff format

Every agent handoff should include:

- **Goal:** what was attempted.
- **Changed files:** exact paths.
- **Commands run:** exact commands and pass/fail status.
- **Result:** what now works.
- **Risks/open questions:** anything unresolved.
- **Next step:** the recommended next action.

## Safety rules for autonomous agents

- Do not run destructive shell commands (`rm -rf`, force push, database reset, mass delete) without explicit human approval.
- Do not install or upgrade global tools unless the human asked for tool setup.
- Do not modify unrelated files.
- Do not touch `.git/` internals directly.
- Do not commit changes you did not inspect.
- If tests fail for unrelated reasons, report that clearly instead of hiding it.

## Definition of done

A task is done only when:

1. The requested behavior or documentation change is implemented.
2. Relevant tests/checks pass, or failures are clearly documented with cause.
3. Migrations are included and verified for schema changes.
4. No secrets or generated junk are staged.
5. The handoff explains what changed and how it was verified.
