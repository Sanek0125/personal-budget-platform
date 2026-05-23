# Personal Budget Platform Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a multi-user personal and family budget platform with FastAPI backend, React frontend, PostgreSQL database, multi-currency accounting, imports from CSV/XLSX/PDF, duplicate protection, custom categories, auto-categorization, splits, budget planning, debts, cashback/bonus accounting, and future Telegram quick-entry support.

**Architecture:** Monorepo with `backend/` FastAPI service, `frontend/` React SPA, `infra/` Docker Compose/PostgreSQL, and `docs/` architecture documentation. Backend owns all domain logic: transaction normalization, duplicate detection, category rules, exchange-rate snapshots, budget calculations, debt balances, imports, and audit log. Frontend consumes REST API and focuses on workflows: dashboard, accounts, transactions, imports, budgets, debts, categories, and settings.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, PostgreSQL 16, Pydantic v2, pytest, React, TypeScript, Vite, TanStack Query, React Router, Tailwind CSS or shadcn/ui, Docker Compose.

---

## 1. Current requirements

Confirmed product decisions:

- Budget can be both personal and family/shared.
- Backend must be FastAPI Python.
- Frontend must be React.
- Database must be PostgreSQL.
- Multiple users are supported.
- User-defined categories are supported.
- Automatic category assignment by transaction description is required.
- Transactions are imported from CSV, Excel, and PDF.
- Duplicate protection is required.
- Multiple currencies are required.
- Cashback and bonus accounting is required.
- Future Telegram integration for quick cash-entry is required.
- Budget planning is required via `budgets` and `budget_limits`.
- Debts are required, including both:
  - I owe someone.
  - Someone owes me.
- Split transactions are required.

Non-goal for this plan: implementation must not start yet. This document only defines the implementation plan and target design.

---

## 2. Repository structure

Create this structure during implementation:

```text
personal-budget-platform/
  .hermes/
    plans/
      2026-05-21_141258-personal-budget-platform.md
  backend/
    app/
      api/
      core/
      db/
      models/
      schemas/
      services/
      workers/
      main.py
    alembic/
    tests/
    pyproject.toml
    alembic.ini
  frontend/
    src/
      app/
      api/
      components/
      features/
      pages/
      routes/
      styles/
    package.json
    vite.config.ts
    tsconfig.json
  infra/
    docker-compose.yml
    postgres/
  docs/
    architecture.md
    database-schema.md
    import-pipeline.md
    duplicate-detection.md
  README.md
```

---

## 3. Domain model overview

Core aggregate roots:

- `User`: login identity and Telegram linkage.
- `Workspace`: personal/family budget space.
- `WorkspaceMember`: membership and permissions.
- `Account`: cash, card, bank account, bonus account, etc.
- `Transaction`: income, expense, transfer, adjustment.
- `TransactionSplit`: category-level breakdown of one transaction.
- `Category`: user-defined hierarchical categories.
- `CategoryRule`: rule-based auto-categorization.
- `ImportBatch` / `ImportRow`: staging layer for uploaded statements.
- `Budget` / `BudgetLimit`: budget planning by period/category/account.
- `Debt` / `DebtPayment`: debts and repayments.
- `RewardProgram` / `RewardEvent`: cashback, points, miles.
- `Currency` / `ExchangeRate`: multi-currency support.
- `AuditLog`: financial-data traceability.

---

## 4. Proposed PostgreSQL tables

### 4.1 Users and workspaces

#### `users`

Purpose: application users and future Telegram linking.

Fields:

- `id uuid primary key`
- `email citext unique null`
- `password_hash text null`
- `display_name text not null`
- `telegram_id bigint unique null`
- `is_active boolean not null default true`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Notes:

- Allow nullable email initially if Telegram-only users are later supported.
- Use `citext` for case-insensitive email uniqueness.

#### `workspaces`

Purpose: personal or family budget container.

Fields:

- `id uuid primary key`
- `name text not null`
- `kind text not null` — `personal`, `family`, `trip`, `other`
- `base_currency_code char(3) not null references currencies(code)`
- `owner_user_id uuid not null references users(id)`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

#### `workspace_members`

Purpose: many-to-many users/workspaces with permissions.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `user_id uuid not null references users(id)`
- `role text not null` — `owner`, `admin`, `member`, `viewer`
- `created_at timestamptz not null`

Constraints:

- `unique(workspace_id, user_id)`

---

### 4.2 Currency support

#### `currencies`

Fields:

- `code char(3) primary key`
- `name text not null`
- `symbol text null`
- `minor_units smallint not null default 2`

#### `exchange_rates`

Fields:

- `id uuid primary key`
- `base_currency_code char(3) not null references currencies(code)`
- `quote_currency_code char(3) not null references currencies(code)`
- `rate numeric(24, 12) not null`
- `rate_date date not null`
- `source text not null` — `manual`, `cbr`, `bank_import`, `api`
- `created_at timestamptz not null`

Constraints:

- `unique(base_currency_code, quote_currency_code, rate_date, source)`

Important rule:

- A transaction must store the rate snapshot used for reporting. Historical reports must not change when exchange-rate data changes later.

---

### 4.3 Accounts

#### `accounts`

Purpose: cards, cash wallets, bank accounts, bonus accounts.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `owner_user_id uuid null references users(id)`
- `name text not null`
- `type text not null` — `bank_card`, `cash`, `bank_account`, `bonus`, `investment`, `crypto`, `other`
- `currency_code char(3) not null references currencies(code)`
- `institution_name text null`
- `masked_number text null`
- `opening_balance numeric(20, 6) not null default 0`
- `is_active boolean not null default true`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Notes:

- `owner_user_id` lets one family workspace contain both shared and personal accounts.
- If `owner_user_id is null`, treat account as shared workspace account.

---

### 4.4 Categories and auto-categorization

#### `categories`

Fields:

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

Constraints:

- `unique(workspace_id, parent_id, name)`

#### `category_rules`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `category_id uuid not null references categories(id)`
- `name text not null`
- `priority int not null default 100`
- `field text not null` — `description`, `merchant_name`, `amount`, `account`, `source`
- `operator text not null` — `contains`, `equals`, `starts_with`, `regex`, `amount_between`
- `value text not null`
- `value_json jsonb null`
- `is_active boolean not null default true`
- `apply_on_import boolean not null default true`
- `created_by_user_id uuid not null references users(id)`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

#### `category_rule_matches`

Fields:

- `id uuid primary key`
- `transaction_id uuid not null references transactions(id)`
- `category_rule_id uuid not null references category_rules(id)`
- `matched_value text null`
- `confidence numeric(5, 4) not null default 1.0`
- `created_at timestamptz not null`

---

### 4.5 Transactions

#### `transactions`

Purpose: canonical ledger entries.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `account_id uuid not null references accounts(id)`
- `user_id uuid null references users(id)`
- `type text not null` — `expense`, `income`, `transfer`, `adjustment`
- `status text not null` — `posted`, `pending`, `deleted`, `duplicate`, `ignored`
- `occurred_at timestamptz not null`
- `booked_at date null`
- `amount numeric(20, 6) not null`
- `currency_code char(3) not null references currencies(code)`
- `original_amount numeric(20, 6) null`
- `original_currency_code char(3) null references currencies(code)`
- `base_amount numeric(20, 6) null`
- `base_currency_code char(3) null references currencies(code)`
- `exchange_rate_id uuid null references exchange_rates(id)`
- `exchange_rate numeric(24, 12) null`
- `description text not null`
- `merchant_name text null`
- `merchant_raw text null`
- `category_id uuid null references categories(id)`
- `category_confidence numeric(5, 4) null`
- `categorized_by text null` — `user`, `rule`, `ml`, `import`
- `notes text null`
- `source text not null` — `manual`, `csv_import`, `excel_import`, `pdf_import`, `telegram`, `api`
- `import_batch_id uuid null references import_batches(id)`
- `import_row_id uuid null references import_rows(id)`
- `external_id text null`
- `fingerprint text not null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`
- `deleted_at timestamptz null`

Constraints and indexes:

- Unique active fingerprint: `unique(workspace_id, account_id, fingerprint) where deleted_at is null`
- Index by `workspace_id, occurred_at desc`
- Index by `account_id, occurred_at desc`
- Index by `category_id`

Business rules:

- Expenses should generally be stored as negative `amount`.
- Income should generally be stored as positive `amount`.
- Transfers are represented as two linked transactions.
- Never physically delete transactions; use `deleted_at` and status.

#### `transaction_splits`

Purpose: split one transaction into multiple categories.

Fields:

- `id uuid primary key`
- `transaction_id uuid not null references transactions(id)`
- `category_id uuid not null references categories(id)`
- `amount numeric(20, 6) not null`
- `currency_code char(3) not null references currencies(code)`
- `description text null`
- `sort_order int not null default 0`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Validation:

- Sum of splits must equal parent transaction amount in transaction currency.
- If splits exist, reports should use splits instead of parent `category_id`.

#### `transaction_links`

Purpose: transfers, refunds, corrections, cashback links, duplicate relations.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `transaction_id uuid not null references transactions(id)`
- `linked_transaction_id uuid not null references transactions(id)`
- `relation_type text not null` — `transfer_pair`, `refund`, `cashback_for`, `correction`, `duplicate_of`, `debt_payment_for`
- `created_at timestamptz not null`

Constraints:

- `unique(transaction_id, linked_transaction_id, relation_type)`

---

### 4.6 Imports and duplicate protection

#### `files`

Purpose: uploaded source file metadata. Actual file may live on disk/S3.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `uploaded_by_user_id uuid not null references users(id)`
- `original_filename text not null`
- `content_type text not null`
- `size_bytes bigint not null`
- `storage_key text not null`
- `sha256 text not null`
- `created_at timestamptz not null`

Constraints:

- `unique(workspace_id, sha256)`

#### `import_batches`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `user_id uuid not null references users(id)`
- `account_id uuid null references accounts(id)`
- `file_id uuid null references files(id)`
- `source_type text not null` — `csv`, `xlsx`, `pdf`
- `source_name text null` — bank/parser name
- `original_filename text not null`
- `file_hash text not null`
- `file_size bigint null`
- `status text not null` — `uploaded`, `parsed`, `processed`, `failed`, `partially_processed`
- `total_rows int not null default 0`
- `imported_count int not null default 0`
- `duplicate_count int not null default 0`
- `error_count int not null default 0`
- `parser_version text null`
- `uploaded_at timestamptz not null`
- `processed_at timestamptz null`

Constraints:

- `unique(workspace_id, file_hash)`

#### `import_rows`

Fields:

- `id uuid primary key`
- `import_batch_id uuid not null references import_batches(id)`
- `workspace_id uuid not null references workspaces(id)`
- `row_number int not null`
- `raw_data jsonb not null`
- `normalized_data jsonb null`
- `raw_hash text not null`
- `normalized_hash text null`
- `status text not null` — `pending`, `imported`, `duplicate`, `possible_duplicate`, `ignored`, `error`
- `error_message text null`
- `transaction_id uuid null references transactions(id)`
- `created_at timestamptz not null`

Constraints:

- `unique(import_batch_id, row_number)`
- `unique(import_batch_id, raw_hash)`

#### `duplicate_candidates`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `import_row_id uuid not null references import_rows(id)`
- `existing_transaction_id uuid not null references transactions(id)`
- `similarity_score numeric(5, 4) not null`
- `reason text not null`
- `status text not null` — `pending`, `confirmed_duplicate`, `not_duplicate`
- `created_at timestamptz not null`
- `resolved_at timestamptz null`

Duplicate strategy:

1. Reject exact duplicate files by `file_hash`.
2. Reject exact duplicate rows by `raw_hash` within one batch.
3. Prefer bank `external_id` if present.
4. Otherwise generate transaction fingerprint from normalized account/date/amount/currency/description/merchant.
5. If exact fingerprint exists, mark `duplicate`.
6. If near match exists, create `duplicate_candidates` and require user confirmation.

---

### 4.7 Budgets and budget limits

#### `budgets`

Purpose: budget plan containers.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `name text not null`
- `period_type text not null` — `monthly`, `weekly`, `yearly`, `custom`
- `start_date date not null`
- `end_date date null`
- `currency_code char(3) not null references currencies(code)`
- `is_active boolean not null default true`
- `created_by_user_id uuid not null references users(id)`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Notes:

- A workspace can have multiple budgets, but only one active monthly budget should usually be used by default.

#### `budget_limits`

Purpose: limits per category/account/user for a budget.

Fields:

- `id uuid primary key`
- `budget_id uuid not null references budgets(id)`
- `workspace_id uuid not null references workspaces(id)`
- `category_id uuid null references categories(id)`
- `account_id uuid null references accounts(id)`
- `user_id uuid null references users(id)`
- `limit_type text not null` — `expense`, `income`, `net`
- `amount numeric(20, 6) not null`
- `currency_code char(3) not null references currencies(code)`
- `rollover boolean not null default false`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Validation:

- At least one dimension should be set: `category_id`, `account_id`, or `user_id`.
- For normal category budgeting, use `category_id` only.

---

### 4.8 Debts

#### `contacts`

Purpose: people or organizations involved in debts who may not be app users.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `name text not null`
- `linked_user_id uuid null references users(id)`
- `phone text null`
- `telegram_id bigint null`
- `notes text null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

#### `debts`

Purpose: money owed either to me or by me.

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `created_by_user_id uuid not null references users(id)`
- `counterparty_contact_id uuid not null references contacts(id)`
- `direction text not null` — `they_owe_me`, `i_owe_them`
- `principal_amount numeric(20, 6) not null`
- `currency_code char(3) not null references currencies(code)`
- `status text not null` — `open`, `partially_paid`, `paid`, `cancelled`
- `description text null`
- `opened_at date not null`
- `due_date date null`
- `source_transaction_id uuid null references transactions(id)`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`
- `closed_at timestamptz null`

Examples:

- `they_owe_me`: I paid 5,000 RUB for a friend; friend should return it.
- `i_owe_them`: friend paid for hotel; I owe them 10,000 RUB.

#### `debt_payments`

Purpose: repayments against debts.

Fields:

- `id uuid primary key`
- `debt_id uuid not null references debts(id)`
- `transaction_id uuid null references transactions(id)`
- `amount numeric(20, 6) not null`
- `currency_code char(3) not null references currencies(code)`
- `paid_at date not null`
- `notes text null`
- `created_at timestamptz not null`

Validation:

- Sum of payments must not exceed principal unless overpayment is explicitly allowed later.
- Debt status is derived or updated from total paid amount.

---

### 4.9 Rewards, bonuses, cashback

#### `reward_programs`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `name text not null`
- `type text not null` — `cashback_money`, `points`, `miles`, `bonus_currency`
- `currency_code char(3) null references currencies(code)`
- `points_unit_name text null`
- `institution_name text null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

#### `reward_events`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `reward_program_id uuid not null references reward_programs(id)`
- `transaction_id uuid null references transactions(id)`
- `event_type text not null` — `accrued`, `redeemed`, `expired`, `adjusted`, `reversed`
- `amount numeric(20, 6) null`
- `currency_code char(3) null references currencies(code)`
- `points_amount numeric(20, 6) null`
- `occurred_at timestamptz not null`
- `description text null`
- `source text not null` — `manual`, `import`, `rule`, `api`
- `created_at timestamptz not null`

#### `cashback_rules`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `reward_program_id uuid not null references reward_programs(id)`
- `category_id uuid null references categories(id)`
- `merchant_pattern text null`
- `percent numeric(7, 4) not null`
- `max_amount numeric(20, 6) null`
- `valid_from date not null`
- `valid_to date null`
- `is_active boolean not null default true`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

---

### 4.10 Telegram future support

#### `telegram_sessions`

Fields:

- `id uuid primary key`
- `user_id uuid not null references users(id)`
- `telegram_chat_id bigint not null`
- `telegram_user_id bigint not null`
- `default_workspace_id uuid null references workspaces(id)`
- `default_account_id uuid null references accounts(id)`
- `state text null`
- `state_data jsonb null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Constraints:

- `unique(telegram_user_id)`

#### `manual_entry_drafts`

Fields:

- `id uuid primary key`
- `workspace_id uuid not null references workspaces(id)`
- `user_id uuid not null references users(id)`
- `source text not null` — `telegram`, `web`
- `raw_text text not null`
- `parsed_data jsonb null`
- `status text not null` — `draft`, `confirmed`, `cancelled`, `failed`
- `transaction_id uuid null references transactions(id)`
- `created_at timestamptz not null`
- `confirmed_at timestamptz null`

---

### 4.11 Audit log

#### `audit_log`

Fields:

- `id uuid primary key`
- `workspace_id uuid null references workspaces(id)`
- `user_id uuid null references users(id)`
- `entity_type text not null`
- `entity_id uuid not null`
- `action text not null` — `create`, `update`, `delete`, `restore`, `import`, `categorize`
- `old_data jsonb null`
- `new_data jsonb null`
- `created_at timestamptz not null`

---

## 5. Backend implementation plan

### Phase 1: Project skeleton

Tasks:

1. Create `backend/pyproject.toml` with FastAPI, SQLAlchemy async, Alembic, asyncpg, Pydantic, pytest.
2. Create `backend/app/main.py` with health endpoint.
3. Create `backend/app/core/config.py` with environment-based settings.
4. Create `backend/app/db/session.py` with async SQLAlchemy engine/session.
5. Create `infra/docker-compose.yml` with PostgreSQL and backend service placeholders.
6. Add backend tests for `/health`.

Validation:

```bash
cd backend
pytest
```

Expected: health test passes.

### Phase 2: Database foundation

Tasks:

1. Configure Alembic async migrations.
2. Add enum strategy. Prefer PostgreSQL enums only for stable values; otherwise use `text` + check constraints for flexibility.
3. Implement models:
   - `User`
   - `Workspace`
   - `WorkspaceMember`
   - `Currency`
   - `ExchangeRate`
4. Create first migration.
5. Add seed migration or seed script for common currencies: RUB, USD, EUR, GEL, KZT, TRY, AED.

Validation:

```bash
cd backend
alembic upgrade head
pytest
```

### Phase 3: Accounts and categories

Tasks:

1. Implement `Account` model and CRUD service.
2. Implement `Category` model with hierarchy support.
3. Implement category CRUD endpoints.
4. Add tests for:
   - creating personal account;
   - creating shared account;
   - creating nested categories;
   - duplicate category name under same parent rejected.

Endpoints draft:

- `GET /workspaces/{workspace_id}/accounts`
- `POST /workspaces/{workspace_id}/accounts`
- `GET /workspaces/{workspace_id}/categories`
- `POST /workspaces/{workspace_id}/categories`

### Phase 4: Transactions and splits

Tasks:

1. Implement `Transaction` model.
2. Implement `TransactionSplit` model.
3. Implement `TransactionLink` model.
4. Add transaction create/list/update/delete endpoints.
5. Implement split validation: split sum equals transaction amount.
6. Implement transfer operation as two transactions plus `transfer_pair` link.
7. Add tests for expense, income, transfer, split transaction, soft delete.

Endpoints draft:

- `GET /workspaces/{workspace_id}/transactions`
- `POST /workspaces/{workspace_id}/transactions`
- `PATCH /transactions/{transaction_id}`
- `DELETE /transactions/{transaction_id}`
- `POST /workspaces/{workspace_id}/transfers`

### Phase 5: Duplicate fingerprints

Tasks:

1. Implement normalization utility:
   - trim whitespace;
   - uppercase description for fingerprint;
   - normalize repeated spaces;
   - normalize amount scale;
   - prefer `external_id` when present.
2. Implement `build_transaction_fingerprint()` service.
3. Add unique index for active transactions.
4. Add tests for:
   - same row rejected;
   - same file row not imported twice;
   - two equal amounts with different descriptions allowed;
   - soft-deleted transaction does not block reimport.

### Phase 6: Import pipeline

Tasks:

1. Implement `File`, `ImportBatch`, `ImportRow`, `DuplicateCandidate` models.
2. Implement upload endpoint.
3. Implement CSV parser.
4. Implement XLSX parser.
5. Implement PDF parser abstraction, with first version limited to text extraction and manual mapping.
6. Implement import staging: file -> batch -> rows -> normalized rows.
7. Implement import preview endpoint.
8. Implement confirm import endpoint.
9. Apply category rules after confirm.

Endpoints draft:

- `POST /workspaces/{workspace_id}/imports/upload`
- `GET /imports/{import_batch_id}`
- `GET /imports/{import_batch_id}/rows`
- `POST /imports/{import_batch_id}/confirm`

### Phase 7: Category rules

Tasks:

1. Implement `CategoryRule` model.
2. Implement `CategoryRuleMatch` model.
3. Implement matching engine with priority order.
4. Add endpoints to manage rules.
5. Add endpoint to re-run rules on existing uncategorized transactions.
6. Add tests for contains, equals, starts_with, regex, amount_between.

Endpoints draft:

- `GET /workspaces/{workspace_id}/category-rules`
- `POST /workspaces/{workspace_id}/category-rules`
- `PATCH /category-rules/{rule_id}`
- `POST /workspaces/{workspace_id}/category-rules/apply`

### Phase 8: Budgets

Tasks:

1. Implement `Budget` model.
2. Implement `BudgetLimit` model.
3. Implement budget CRUD endpoints.
4. Implement budget progress service using transactions and splits.
5. Support monthly period first.
6. Add tests for:
   - monthly category budget;
   - split transactions counted by split category;
   - base currency conversion;
   - shared/family workspace budget.

Endpoints draft:

- `GET /workspaces/{workspace_id}/budgets`
- `POST /workspaces/{workspace_id}/budgets`
- `GET /budgets/{budget_id}/progress`
- `POST /budgets/{budget_id}/limits`

### Phase 9: Debts

Tasks:

1. Implement `Contact` model.
2. Implement `Debt` model.
3. Implement `DebtPayment` model.
4. Add debt CRUD endpoints.
5. Add repayment flow linked to transaction.
6. Add debt balance service.
7. Add tests for:
   - `they_owe_me` debt;
   - `i_owe_them` debt;
   - partial repayment;
   - full repayment closes debt;
   - debt created from transaction.

Endpoints draft:

- `GET /workspaces/{workspace_id}/debts`
- `POST /workspaces/{workspace_id}/debts`
- `POST /debts/{debt_id}/payments`
- `GET /workspaces/{workspace_id}/debts/summary`

### Phase 10: Rewards and cashback

Tasks:

1. Implement `RewardProgram` model.
2. Implement `RewardEvent` model.
3. Implement `CashbackRule` model.
4. Add manual reward event creation.
5. Add linking cashback to source transactions.
6. Add expected cashback calculation from rules.
7. Add tests for money cashback and points/miles.

Endpoints draft:

- `GET /workspaces/{workspace_id}/reward-programs`
- `POST /workspaces/{workspace_id}/reward-programs`
- `POST /workspaces/{workspace_id}/reward-events`
- `GET /workspaces/{workspace_id}/rewards/summary`

### Phase 11: Audit log

Tasks:

1. Implement audit log model.
2. Add audit helper service.
3. Log transaction create/update/delete/import/categorize.
4. Log category and budget changes.
5. Add tests that audit entries are created for financial mutations.

### Phase 12: Auth, sessions, and permissions

Purpose: replace the temporary `X-User-Id` development-auth flow before the app is treated as usable from a normal browser. Without this phase, the frontend cannot know which user's workspaces to load when a visitor opens the app without a preconfigured `VITE_DEV_USER_ID`.

Tasks:

1. Choose the first production auth mechanism. Default MVP recommendation: classic email/password with server-issued session/JWT; keep Telegram/OAuth as later login providers.
2. Add password hashing and auth schemas for register/login/logout/current-user flows.
3. Add backend endpoints:
   - `POST /auth/register` — create a user and initial personal workspace or return enough state for onboarding;
   - `POST /auth/login` — authenticate and establish a session/JWT;
   - `POST /auth/logout` — clear/revoke the session when applicable;
   - `GET /auth/me` — return the authenticated user profile.
4. Replace temporary request identity for browser traffic:
   - authenticated requests derive `current_user` from the session/JWT;
   - keep `X-User-Id` only as an explicit local/dev fallback, not as the normal frontend path;
   - unauthenticated workspace-scoped requests return `401` instead of falling back to a default user.
5. Implement workspace membership checks and role-based permission helpers.
6. Apply authorization dependencies to all workspace endpoints.
7. Add tests for unauthenticated access, invalid credentials, `/auth/me`, viewer/member/admin/owner permissions, and workspace isolation.

Open decision:

- Exact long-term auth mechanism: email/password, magic links, Telegram login, OAuth, or a combination. For the next MVP step, use email/password unless product direction changes.

### Phase 13: Frontend auth gate and onboarding

Purpose: make the React app safe to open without preconfigured development auth, and ensure workspace loading happens only after the frontend knows the authenticated user.

Tasks:

1. Add an auth client/module for `/auth/register`, `/auth/login`, `/auth/logout`, and `/auth/me`.
2. Add login/register pages and route unauthenticated users there before rendering the workspace shell.
3. Change the shell startup flow:
   - first load `/auth/me`;
   - only then load `/workspaces` for the authenticated user;
   - show a clear unauthenticated state instead of sending workspace requests with a hardcoded user id.
4. Store auth state safely:
   - prefer an HttpOnly cookie session if backend supports it;
   - otherwise store a short-lived bearer token deliberately and centralize token injection in the API client.
5. Preserve the existing workspace switcher after login:
   - keep `personal-budget.active-workspace-id` as a UI preference;
   - validate the stored workspace id against the authenticated user's workspace list;
   - clear/fallback when the user changes or the workspace is no longer available.
6. Add onboarding for users with no workspaces: create a first personal workspace before showing core budget pages.
7. Add frontend tests for unauthenticated redirect, login success, `/auth/me` bootstrap, no-workspace onboarding, logout, and workspace-switcher persistence per authenticated user.

### Phase 14: User management and workspace invitations

Purpose: make development and family/shared workspaces usable without direct SQL while full production auth is still undecided.

Tasks:

1. Add user-management schemas and endpoints:
   - `POST /users` — create a user with optional email/Telegram linkage and display name;
   - `GET /users/{user_id}` — fetch a user by id;
   - `GET /users?email=...` — find users by normalized email for adding to workspaces.
2. Add workspace member management:
   - `POST /workspaces/{workspace_id}/members` — add an existing user as `admin`, `member`, or `viewer`;
   - later: `PATCH /workspaces/{workspace_id}/members/{member_id}` for role changes;
   - later: `DELETE /workspaces/{workspace_id}/members/{member_id}` for removal.
3. Permission rule for this temporary phase:
   - user creation remains open/dev-friendly until real auth exists;
   - adding members requires current requester to be workspace `owner` or `admin`;
   - do not allow creating a second `owner` through the add-member endpoint.
4. Update frontend/dev docs so local users can be created through HTTP and then used via `VITE_DEV_USER_ID`.
5. Add tests for user creation, email normalization, duplicate handling, member-add permissions, missing users, and duplicate memberships.

Endpoints draft:

- `POST /users`
- `GET /users/{user_id}`
- `GET /users?email={email}`
- `POST /workspaces/{workspace_id}/members`

---

## 6. Frontend implementation plan

### Phase 1: Frontend skeleton

Tasks:

1. Create React + TypeScript + Vite app in `frontend/`.
2. Configure routing with React Router.
3. Configure TanStack Query.
4. Configure API client.
5. Add base layout with sidebar and workspace switcher placeholder.

### Phase 2: Core pages

Pages:

- `/` dashboard
- `/transactions`
- `/accounts`
- `/categories`
- `/imports`
- `/budgets`
- `/debts`
- `/rewards`
- `/settings`

### Phase 3: Transactions UX

Features:

- Transaction list with date/category/account filters.
- Manual transaction form.
- Split editor.
- Transfer form.
- Soft-delete/restore UX.

### Phase 4: Import UX

Features:

- File upload.
- Account selection.
- Import preview table.
- Duplicate/possible duplicate badges.
- Mapping UI for unknown CSV/XLSX columns.
- Confirm import.

### Phase 5: Budget UX

Features:

- Budget list.
- Monthly budget editor.
- Category limits.
- Progress bars.
- Over-budget warnings.

### Phase 6: Debts UX

Features:

- Contact list.
- Debt list grouped by direction.
- Debt detail with repayments.
- Create debt from transaction.
- Summary: total owed to me / total I owe.

---

## 7. API design conventions

Use REST first.

Conventions:

- All workspace-scoped routes include `workspace_id`.
- Use UUID path params.
- Use Pydantic request/response schemas.
- Use pagination for lists.
- Use `created_at` and `updated_at` everywhere.
- For money amounts, send strings in JSON to avoid JS float issues.

Example response amount:

```json
{
  "amount": "-1234.56",
  "currency_code": "RUB"
}
```

---

## 8. Testing strategy

Backend tests:

- Unit tests for normalization, fingerprinting, category rules, budget calculations, debt balances.
- Integration tests against PostgreSQL for migrations and repositories.
- API tests using `httpx.AsyncClient`.

Frontend tests:

- Component tests for forms and tables.
- API-client tests with mocked responses.
- E2E smoke tests later with Playwright.

Minimum validation before merging each implementation phase:

```bash
cd backend
pytest
alembic upgrade head

cd ../frontend
npm test
npm run build
```

---

## 9. Important risks and tradeoffs

### Duplicate detection risk

Bank statements can contain legitimate same-day repeated payments with same amount and similar description. Exact fingerprinting can create false positives.

Mitigation:

- Exact duplicate only when confidence is high.
- Use `possible_duplicate` for fuzzy cases.
- Let user resolve duplicate candidates.

### PDF import risk

PDF statements vary wildly by bank.

Mitigation:

- Build parser interface.
- Start with CSV/XLSX as first-class import types.
- For PDF, start with text extraction + manually configured parser profiles.

### Multi-currency reporting risk

Historical reports can change if rates are recalculated dynamically.

Mitigation:

- Store `base_amount`, `base_currency_code`, and `exchange_rate` on transaction.
- Allow manual correction of exchange rate per transaction.

### Family budget privacy risk

Family workspace may contain personal and shared accounts.

Mitigation:

- `accounts.owner_user_id` distinguishes personal from shared.
- Add account-level visibility later if needed.

### Split transaction reporting risk

Counting both parent category and splits can double-count.

Mitigation:

- If splits exist, reports use splits.
- Parent `category_id` becomes fallback/default only.

---

## 10. Open product questions before implementation

1. Auth: should the first version use email/password, magic links, Telegram login, or no auth while local-only?
2. UI language: Russian-only first, or prepare i18n from the start?
3. Deployment target: local Docker, VPS, cloud, or Raspberry Pi?
4. File storage: local filesystem first or S3-compatible storage?
5. Exchange rates: manual first or automatic CBR/API integration from MVP?
6. Bank import mapping: should users configure column mapping manually in UI, or should we start with fixed parser profiles?
7. Privacy in family workspace: can all members see all accounts, or do we need account-level permissions immediately?

---

## 11. Suggested implementation order

Recommended order from the current frontend Dashboard/workspace-switcher state:

1. Backend production-auth foundation: register/login/logout/current-user, session/JWT validation, unauthenticated `401` behavior, and role-aware workspace authorization.
2. Frontend auth gate: login/register routes, `/auth/me` bootstrap, no-workspace onboarding, and workspace loading only after the user is known.
3. Keep the workspace switcher as a post-login workspace preference, validated against the authenticated user's workspace list.
4. Then continue deeper finance workflows: transaction filters/splits/transfers, import mapping, budget limits/progress, debt repayments, reward rules, reporting, and Telegram quick-entry prototype.

Original domain build order, kept for historical context:

1. Backend skeleton + PostgreSQL + migrations.
2. Users/workspaces/members.
3. Accounts/categories.
4. Transactions/splits/transfers.
5. Duplicate fingerprints.
6. CSV/XLSX imports.
7. Category rules.
8. Budgets.
9. Debts.
10. Rewards/cashback.
11. User-management API for creating users and adding workspace members during the dev-auth phase.
12. React frontend core.
13. Import UI.
14. Budget/debt/reward UI.
15. Telegram quick-entry prototype.

Reasoning:

- Transactions are the center of the product.
- Imports depend on accounts/categories/transactions.
- Budgets and debts depend on transaction semantics.
- Cashback can be layered after transactions/categories are stable.
- Telegram should come after manual transaction creation is already reliable.

---

## 12. Definition of done for MVP

MVP is complete when:

- User can create a personal or family workspace.
- User can create accounts in multiple currencies.
- User can create categories and subcategories.
- User can manually create income/expense/transfer transactions.
- User can split a transaction across categories.
- User can import CSV/XLSX statements into staging.
- System prevents obvious duplicates.
- User can confirm import and see imported transactions.
- User can create auto-categorization rules and apply them.
- User can create monthly budget limits and see progress.
- User can record debts in both directions and repayments.
- User can record cashback/bonus events linked to transactions.
- Frontend supports the core flows above.
- Backend tests cover core financial logic.

---

## 13. Do not implement yet

This repository currently contains only the planning document. Do not create backend/frontend code until explicitly instructed to start implementation.
