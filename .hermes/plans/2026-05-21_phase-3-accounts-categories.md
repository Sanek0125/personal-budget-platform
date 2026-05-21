# Phase 3 Slice — Accounts and Categories

## Goal

Implement the next backend phase from `.hermes/plans/2026-05-21_141258-personal-budget-platform.md`: accounts and categories foundation.

## Scope

Implement a small, reviewable backend slice:

1. `Account` SQLAlchemy model.
2. `Category` SQLAlchemy model with parent/child hierarchy support.
3. Alembic migration for `accounts` and `categories`.
4. Minimal Pydantic schemas needed for account/category CRUD.
5. Minimal FastAPI endpoints:
   - `GET /workspaces/{workspace_id}/accounts`
   - `POST /workspaces/{workspace_id}/accounts`
   - `GET /workspaces/{workspace_id}/categories`
   - `POST /workspaces/{workspace_id}/categories`
6. Tests for:
   - creating a personal account (`owner_user_id` set);
   - creating a shared account (`owner_user_id` null);
   - creating nested categories;
   - duplicate category name under the same parent is rejected.

## Constraints

- Follow `AGENTS.md` and `.hermes/workflows/multi-agent-development.md`.
- Use strict TDD: write failing tests first and run them before implementation.
- Keep changes scoped to backend accounts/categories plus necessary routing/schema/migration wiring.
- Do not implement transactions/imports/auth/permissions yet.
- Do not read or print secrets. Do not touch `.env`.
- Do not run destructive commands.
- Do not push or open the PR yourself if credentials/gh are unavailable; leave a clean commit and handoff for the integrator.

## Expected model fields

### Account

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `owner_user_id uuid null references users(id)`
- `name text not null`
- `type text not null` — initially free text/check constraint is okay
- `currency_code char(3) not null references currencies(code)`
- `institution_name text null`
- `masked_number text null`
- `opening_balance numeric(20, 6) not null default 0`
- `is_active boolean not null default true`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

### Category

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `parent_id uuid null references categories(id)`
- `name text not null`
- `type text not null` — `expense`, `income`, `transfer`, `mixed`
- `color text null`
- `icon text null`
- `is_system boolean not null default false`
- `sort_order int not null default 0`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

## Important constraints/indexes

- `categories`: unique category name under the same parent in a workspace. PostgreSQL unique indexes treat NULL parent IDs specially, so root categories also need duplicate protection. Use a robust implementation that rejects duplicates for both root and nested categories.
- Add useful indexes for `workspace_id` on both tables.
- Keep ORM metadata and Alembic migration in sync.

## Validation commands

Run from `backend/`:

```bash
uv run ruff check .
uv run pytest -q
uv run alembic downgrade base
uv run alembic upgrade head
```

If PostgreSQL is not running for Alembic, report the exact failure and still run all checks that do not require external services.

## Handoff

Return the standard AGENTS.md handoff format with changed files, commands run, result, risks/open questions, and next step.
