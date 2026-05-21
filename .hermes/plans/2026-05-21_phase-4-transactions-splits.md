# Phase 4 Plan — Transactions, Splits, Transfers

**Repo:** `/home/primalex/projects/personal-budget-platform`
**Branch:** `feat/transactions-splits`
**Plan file:** `.hermes/plans/2026-05-21_phase-4-transactions-splits.md`
**Parent plan:** `.hermes/plans/2026-05-21_141258-personal-budget-platform.md` Phase 4
**Role:** Planner only — do not implement production code in this planning task.

## 1. Goal

Implement the backend MVP transaction ledger slice:

- `Transaction`, `TransactionSplit`, and `TransactionLink` SQLAlchemy models.
- Alembic migration for the new tables, constraints, and indexes.
- Pydantic schemas for transaction create/list/read/update/delete and transfer creation.
- FastAPI endpoints for manual API-first CRUD/listing and transfer creation.
- Split validation: split totals must equal the parent transaction amount in transaction currency.
- Transfer operation: create two linked transactions in one DB transaction.
- Soft delete only: never physically delete transactions.
- Tests covering expense, income, transfer, split validation, update, list filtering, and soft delete.

## 2. Scope boundaries

In scope:

- Manual transaction API only.
- Personal/family workspace MVP using the existing fake/dev-user style; no complex auth or permissions.
- Expense amounts are negative; income amounts are positive.
- Category is optional.
- Balances remain derived from accounts plus non-deleted transactions; do not add `current_balance`.
- Store currency/exchange snapshot fields; no automatic exchange-rate fetching.
- Minimal deterministic transaction fingerprint only if the table requires a non-null `fingerprint`.

Out of scope:

- Imports (`ImportBatch`, `ImportRow`, files, CSV/XLSX/PDF parsing).
- Budgets, reports, analytics, debts, cashback/rewards.
- Real auth, permissions, roles, ownership enforcement beyond existing workspace/account/category consistency checks.
- Frontend work.
- Complex duplicate-detection service. Do not add fuzzy duplicate candidates or import duplicate workflows.
- Hard deletes.

## 3. Product/default decisions to preserve

- MVP supports personal and family workspaces, but current dev-user/fake-current-user assumptions remain acceptable.
- Transactions are manual API-first in this phase.
- Store monetary values as `Decimal`/`Numeric`, never float.
- Use uppercase ISO-like 3-letter currency codes.
- `expense` amount must be `< 0`.
- `income` amount must be `> 0`.
- `transfer` is represented by two linked transaction rows:
  - source account transaction: negative amount.
  - destination account transaction: positive amount.
  - both connected by `transaction_links.relation_type = 'transfer_pair'`.
- Category is optional for parent transaction and for non-split transactions.
- Splits are optional; when present, each split has a category and the split amount sum must equal parent transaction amount exactly after Decimal normalization.
- Soft delete means setting `status = 'deleted'` and `deleted_at` to current time; list endpoints exclude deleted by default.

## 4. Current code patterns observed

Use the existing accounts/categories implementation style:

- Models use SQLAlchemy 2 typed declarative style under `backend/app/models/`.
- Schemas live under `backend/app/schemas/` and use Pydantic v2 validators.
- Routes live under `backend/app/api/` with prefixes nested below `/workspaces/{workspace_id}/...`.
- Routes use `Annotated[AsyncSession, Depends(get_db_session)]` and simple `select(...)` statements.
- `IntegrityError` is translated to `HTTPException` with rollback.
- Tests currently use direct async route function calls and small fake async session objects for route behavior.
- `backend/app/models/__init__.py` imports every model so Alembic metadata can discover tables.
- `backend/app/main.py` includes feature routers explicitly.
- Migration revision naming pattern is `20260521_000N_<feature>.py`.

## 5. Files to create or modify

Create:

- `backend/app/models/transaction.py`
- `backend/app/schemas/transaction.py`
- `backend/app/api/transactions.py`
- `backend/alembic/versions/20260521_0003_transactions_splits.py`
- `backend/tests/test_transactions.py`

Modify:

- `backend/app/models/__init__.py`
  - Export `Transaction`, `TransactionSplit`, `TransactionLink`.
- `backend/app/schemas/__init__.py`
  - Export transaction schemas if existing schema package conventions require it.
- `backend/app/main.py`
  - Include the transactions router.

Do not modify:

- Frontend files.
- Import/budget/auth-related files.
- Account/category behavior except where tests need fixtures/data.

## 6. Proposed data model

### 6.1 `transactions`

Fields:

- `id uuid primary key`, default `gen_random_uuid()`.
- `workspace_id uuid not null references workspaces(id) on delete cascade`.
- `account_id uuid not null references accounts(id) on delete restrict`.
- `user_id uuid null references users(id) on delete set null`.
- `type text not null` with check: `expense`, `income`, `transfer`, `adjustment`.
- `status text not null default 'posted'` with check: `posted`, `pending`, `deleted`, `duplicate`, `ignored`.
- `occurred_at timestamptz not null`.
- `booked_at date null`.
- `amount numeric(20, 6) not null`.
- `currency_code char/string(3) not null references currencies(code)`.
- `original_amount numeric(20, 6) null`.
- `original_currency_code char/string(3) null references currencies(code)`.
- `base_amount numeric(20, 6) null`.
- `base_currency_code char/string(3) null references currencies(code)`.
- `exchange_rate_id uuid null references exchange_rates(id)`.
- `exchange_rate numeric(24, 12) null`.
- `description text not null`.
- `merchant_name text null`.
- `merchant_raw text null`.
- `category_id uuid null references categories(id) on delete set null`.
- `category_confidence numeric(5, 4) null`.
- `categorized_by text null` with optional check: `user`, `rule`, `ml`, `import` if non-null.
- `notes text null`.
- `source text not null default 'manual'` with check: `manual`, `csv_import`, `excel_import`, `pdf_import`, `telegram`, `api`.
- `external_id text null`.
- `fingerprint text not null`.
- `created_at timestamptz not null default now()`.
- `updated_at timestamptz not null default now()`.
- `deleted_at timestamptz null`.

Do not add `import_batch_id` or `import_row_id` in Phase 4 unless prior migrations already include those tables. Parent plan references them, but imports are out of scope and FK targets do not exist yet.

Constraints/indexes:

- `ck_transactions_type`.
- `ck_transactions_status`.
- `ck_transactions_source`.
- `ck_transactions_expense_negative`: `type != 'expense' OR amount < 0`.
- `ck_transactions_income_positive`: `type != 'income' OR amount > 0`.
- `ck_transactions_transfer_nonzero`: `type != 'transfer' OR amount != 0`.
- `ck_transactions_adjustment_nonzero`: optional, `type != 'adjustment' OR amount != 0`.
- Partial unique index: `uq_transactions_active_fingerprint` on `(workspace_id, account_id, fingerprint)` where `deleted_at IS NULL`.
- Index `ix_transactions_workspace_occurred_at` on `(workspace_id, occurred_at DESC)`.
- Index `ix_transactions_account_occurred_at` on `(account_id, occurred_at DESC)`.
- Index `ix_transactions_category_id` on `category_id`.
- Index `ix_transactions_status` on `status` only if list filtering needs it.

### 6.2 `transaction_splits`

Fields:

- `id uuid primary key`, default `gen_random_uuid()`.
- `transaction_id uuid not null references transactions(id) on delete cascade`.
- `category_id uuid not null references categories(id) on delete restrict`.
- `amount numeric(20, 6) not null`.
- `currency_code char/string(3) not null references currencies(code)`.
- `description text null`.
- `sort_order int not null default 0`.
- `created_at timestamptz not null default now()`.
- `updated_at timestamptz not null default now()`.

Constraints/indexes:

- Index `ix_transaction_splits_transaction_id` on `transaction_id`.
- Index `ix_transaction_splits_category_id` on `category_id`.
- Optional check `ck_transaction_splits_amount_nonzero`: `amount != 0`.

Business validation in API/service layer:

- All split currencies must equal parent transaction `currency_code`.
- Split amount sum must equal parent transaction `amount`.
- Split categories must belong to the same workspace.
- Splits should not be accepted for transfer transactions in the MVP unless explicitly needed later. Transfers are modeled by links instead.

### 6.3 `transaction_links`

Fields:

- `id uuid primary key`, default `gen_random_uuid()`.
- `workspace_id uuid not null references workspaces(id) on delete cascade`.
- `transaction_id uuid not null references transactions(id) on delete cascade`.
- `linked_transaction_id uuid not null references transactions(id) on delete cascade`.
- `relation_type text not null` with check: `transfer_pair`, `refund`, `cashback_for`, `correction`, `duplicate_of`, `debt_payment_for`.
- `created_at timestamptz not null default now()`.

Constraints/indexes:

- `ck_transaction_links_relation_type`.
- `ck_transaction_links_not_self`: `transaction_id <> linked_transaction_id`.
- Unique constraint `uq_transaction_links_pair_type` on `(transaction_id, linked_transaction_id, relation_type)`.
- Index `ix_transaction_links_workspace_id` on `workspace_id`.
- Index `ix_transaction_links_transaction_id` on `transaction_id`.
- Index `ix_transaction_links_linked_transaction_id` on `linked_transaction_id`.

For transfer creation, create reciprocal links only if API consumers need bidirectional navigation. Minimal MVP can create one link from source to destination and query either direction with `OR`; if choosing one-way links, document it in tests and schema. Prefer one-way link to match parent plan's unique pair constraint and avoid duplicate rows.

## 7. Proposed schemas

Create `backend/app/schemas/transaction.py`.

Types:

- `TransactionType = Literal['expense', 'income', 'transfer', 'adjustment']`
- `TransactionStatus = Literal['posted', 'pending', 'deleted', 'duplicate', 'ignored']`
- `TransactionSource = Literal['manual', 'csv_import', 'excel_import', 'pdf_import', 'telegram', 'api']`
- `TransactionLinkRelationType = Literal['transfer_pair', 'refund', 'cashback_for', 'correction', 'duplicate_of', 'debt_payment_for']`

Schemas:

- `TransactionSplitCreate`
  - `category_id: UUID`
  - `amount: Decimal`
  - `currency_code: str = Field(min_length=3, max_length=3)` normalized uppercase
  - `description: str | None = None`
  - `sort_order: int = 0`
- `TransactionSplitRead(TransactionSplitCreate)`
  - `id: UUID`
  - `transaction_id: UUID`
  - `model_config = {'from_attributes': True}`
- `TransactionCreate`
  - `account_id: UUID`
  - `type: Literal['expense', 'income', 'adjustment']` for manual create; exclude `transfer` to force transfer endpoint.
  - `occurred_at: datetime`
  - `booked_at: date | None = None`
  - `amount: Decimal`
  - `currency_code: str`
  - `original_amount: Decimal | None = None`
  - `original_currency_code: str | None = None`
  - `base_amount: Decimal | None = None`
  - `base_currency_code: str | None = None`
  - `exchange_rate_id: UUID | None = None`
  - `exchange_rate: Decimal | None = None`
  - `description: str = Field(min_length=1)`
  - `merchant_name: str | None = None`
  - `merchant_raw: str | None = None`
  - `category_id: UUID | None = None`
  - `notes: str | None = None`
  - `source: Literal['manual', 'api'] = 'manual'` for manual MVP
  - `external_id: str | None = None`
  - `splits: list[TransactionSplitCreate] = []`
- `TransactionUpdate`
  - All editable fields optional: `occurred_at`, `booked_at`, `amount`, `currency_code`, exchange snapshot fields, `description`, merchant fields, `category_id`, `notes`, `splits`.
  - Do not allow changing `type` between expense/income/transfer in MVP unless tests explicitly cover it; safer: keep type immutable.
  - Do not allow changing `status` directly except soft delete endpoint.
- `TransactionRead`
  - All response fields including `id`, `workspace_id`, `account_id`, `type`, `status`, amount/currency fields, optional category, notes, source, fingerprint, timestamps, `deleted_at`, and `splits: list[TransactionSplitRead] = []`.
- `TransferCreate`
  - `from_account_id: UUID`
  - `to_account_id: UUID`
  - `occurred_at: datetime`
  - `from_amount: Decimal` expected positive input; service stores negative source amount.
  - `from_currency_code: str`
  - `to_amount: Decimal | None = None`; if omitted and currencies match, use same absolute amount.
  - `to_currency_code: str | None = None`; default destination account currency.
  - `exchange_rate: Decimal | None = None`
  - `exchange_rate_id: UUID | None = None`
  - `description: str = Field(min_length=1)`
  - `notes: str | None = None`
  - `booked_at: date | None = None`
- `TransferRead`
  - `outflow: TransactionRead`
  - `inflow: TransactionRead`
  - `link_id: UUID`

Validation in schemas:

- Normalize currency codes to uppercase for all currency fields.
- Expense amount must be negative.
- Income amount must be positive.
- Manual transfer endpoint `from_amount` must be positive and non-zero.
- Decimals should be quantized or compared exactly as `Decimal`; do not convert to float.

## 8. Proposed endpoints

Create `backend/app/api/transactions.py` with router:

```python
router = APIRouter(prefix='/workspaces/{workspace_id}/transactions', tags=['transactions'])
```

Endpoints:

1. `GET /workspaces/{workspace_id}/transactions`
   - Response: `list[TransactionRead]`.
   - Query params:
     - `account_id: UUID | None = None`
     - `category_id: UUID | None = None`
     - `type: TransactionType | None = None`
     - `include_deleted: bool = False`
     - `limit: int = 100` with sane max, e.g. 500.
     - `offset: int = 0`.
   - Default ordering: `occurred_at desc`, then `created_at desc`.
   - Exclude `deleted_at IS NOT NULL` unless `include_deleted=True`.

2. `POST /workspaces/{workspace_id}/transactions`
   - Request: `TransactionCreate`.
   - Response: `TransactionRead`.
   - Status: `201`.
   - Validates workspace exists.
   - Validates account belongs to workspace.
   - Validates optional category belongs to workspace.
   - Validates split categories belong to workspace.
   - Validates split sum/currency if splits are present.
   - Generates minimal deterministic fingerprint if not supplied internally:
     - Suggested input: `workspace_id|account_id|type|occurred_at.isoformat()|amount|currency|description|external_id or ''`.
     - Use SHA-256 hex via Python stdlib.
     - Do not create a separate duplicate service in Phase 4.
   - Flush parent transaction before adding splits.
   - Translate unique fingerprint conflicts to `409 Conflict` with a clear message such as `Transaction fingerprint already exists for this account`.

3. `GET /workspaces/{workspace_id}/transactions/{transaction_id}`
   - Response: `TransactionRead`.
   - Returns `404` if transaction is not in workspace or is soft-deleted, unless optional `include_deleted` is provided. Keep MVP simple: no include flag for detail; deleted returns 404.

4. `PATCH /workspaces/{workspace_id}/transactions/{transaction_id}`
   - Request: `TransactionUpdate`.
   - Response: `TransactionRead`.
   - Reject updates to deleted transactions with `404` or `409`; prefer `404` consistent with hidden deleted resources.
   - Re-run amount sign validation and split validation.
   - If replacing splits, delete old split rows for the transaction and insert new ones in the same transaction.
   - Regenerate fingerprint if fields that feed fingerprint changed.

5. `DELETE /workspaces/{workspace_id}/transactions/{transaction_id}`
   - Soft delete only.
   - Response: `204 No Content` or `TransactionRead`; choose `204` for simple API semantics.
   - Sets `status = 'deleted'`, `deleted_at = now()`.
   - Does not physically delete transaction rows or split/link rows.
   - For a transfer pair, MVP should soft-delete only the requested transaction unless implementing paired delete is explicitly tested. Recommended for user safety: if a transaction has a `transfer_pair` link, soft-delete both sides in one DB transaction and document in tests.

6. `POST /workspaces/{workspace_id}/transactions/transfers`
   - Request: `TransferCreate`.
   - Response: `TransferRead`.
   - Status: `201`.
   - Validates both accounts exist in same workspace and are different.
   - Creates source `Transaction(type='transfer', amount=-abs(from_amount), account_id=from_account_id, currency_code=from_currency_code)`.
   - Creates destination `Transaction(type='transfer', amount=abs(to_amount), account_id=to_account_id, currency_code=to_currency_code)`.
   - If `to_amount` omitted and currencies match, use same absolute amount.
   - If currencies differ, require `to_amount` or exchange snapshot data; do not fetch rates.
   - Creates one `TransactionLink(relation_type='transfer_pair')` connecting source to destination.
   - Commits atomically.

## 9. Implementation sequence with TDD

### Step 0 — Pre-flight

Commands:

```bash
cd /home/primalex/projects/personal-budget-platform
git status --short --branch
```

Expected:

- On `feat/transactions-splits`.
- No unexpected user changes before editing.

### Step 1 — Model and migration tests first

Create/extend tests in `backend/tests/test_transactions.py`:

- `test_transaction_models_are_registered_with_metadata`
  - Assert `Transaction`, `TransactionSplit`, `TransactionLink` table names.
  - Assert all three tables are present in `Base.metadata.tables`.
- `test_transaction_model_has_expected_constraints_and_indexes`
  - Assert check constraints and important indexes exist.
  - Assert partial unique active fingerprint index includes `deleted_at IS NULL`.
- `test_transaction_relationship_annotations_are_configured`
  - Use `inspect(...)` like accounts/categories tests.
  - Assert transaction relationships include `workspace`, `account`, `category`, `currency`, `splits` as applicable.

Run and verify failure:

```bash
cd backend
uv run pytest -q tests/test_transactions.py
```

Expected initial failure:

- Imports fail because models do not exist.

Then implement:

- `backend/app/models/transaction.py`.
- Exports in `backend/app/models/__init__.py`.
- Alembic migration `backend/alembic/versions/20260521_0003_transactions_splits.py`.

Re-run:

```bash
cd backend
uv run pytest -q tests/test_transactions.py
```

### Step 2 — Schema validation tests first

Add tests:

- `test_transaction_schema_normalizes_currency_codes`.
- `test_transaction_schema_requires_expense_negative`.
- `test_transaction_schema_requires_income_positive`.
- `test_transfer_schema_accepts_positive_from_amount_and_normalizes_codes`.
- `test_transfer_schema_rejects_non_positive_from_amount`.
- `test_split_schema_normalizes_currency_code`.

Expected initial failure:

- `app.schemas.transaction` missing.

Then implement `backend/app/schemas/transaction.py`.

Re-run narrow schema tests.

### Step 3 — Transaction create/list tests first

Add fake session support in `test_transactions.py`, following the existing `_FakeAsyncSession` pattern but with enough result types for:

- `.scalar_one_or_none()`.
- `.scalars().all()` for list responses.
- `.add()` / `.add_all()` if used.
- `.delete()` if replacing splits in update.
- `.flush()` if parent IDs are needed before adding splits.
- `.commit()`, `.rollback()`, `.refresh()`.

Test cases:

- `test_create_expense_transaction_creates_posted_manual_transaction`
  - Workspace exists.
  - Account belongs to workspace and currency matches request or request currency is accepted if explicit.
  - No category.
  - No splits.
  - Asserts amount negative, status posted, source manual, fingerprint populated, commit/refresh called.
- `test_create_income_transaction_with_optional_category`
  - Validates category in same workspace.
  - Asserts category_id set.
- `test_create_transaction_rejects_account_outside_workspace`
  - Raises 404 or 422; prefer `404` with `Account not found in this workspace`.
- `test_create_transaction_rejects_category_outside_workspace`
  - Raises `404` with `Category not found in this workspace`.
- `test_create_transaction_translates_duplicate_fingerprint_to_conflict`
  - Simulate `IntegrityError` and assert `409`.
- `test_list_transactions_excludes_deleted_by_default`
  - Verify query construction enough for fake-session style, or return list from fake and assert endpoint output. If query assertions are brittle, keep behavioral test for return shape and add integration coverage later.

Expected initial failure:

- `app.api.transactions` missing.

Then implement create/list endpoints and include router in `backend/app/main.py`.

### Step 4 — Split validation tests first

Add tests:

- `test_create_transaction_with_valid_splits_adds_split_rows`
  - Parent amount `-100.00`.
  - Splits `-60.00`, `-40.00` with same currency.
  - Asserts split rows added with parent transaction ID after flush.
- `test_create_transaction_rejects_split_sum_mismatch`
  - Parent amount `-100.00`; splits total `-90.00`; expect `422`.
- `test_create_transaction_rejects_split_currency_mismatch`
  - Parent currency `USD`; split currency `EUR`; expect `422`.
- `test_create_transaction_rejects_split_category_outside_workspace`
  - Expect `404` or `422`; prefer `404` with `Split category not found in this workspace`.
- `test_create_transaction_rejects_splits_for_transfer_type_if_create_schema_allows_transfer`
  - If normal create schema excludes transfer, this is covered at schema level instead.

Then implement helper functions inside `backend/app/api/transactions.py` or a small service module only if route becomes too large.

Recommended helper functions:

- `_ensure_workspace_exists(session, workspace_id)`.
- `_get_workspace_account(session, workspace_id, account_id)`.
- `_ensure_category_in_workspace(session, workspace_id, category_id, detail)`.
- `_validate_splits(parent_amount, parent_currency, splits)`.
- `_generate_transaction_fingerprint(...)`.

Keep helpers in `api/transactions.py` for Phase 4 unless complexity demands `backend/app/services/transactions.py`. If adding a service file, list it in changed files and keep endpoint thin.

### Step 5 — Transfer tests first

Add tests:

- `test_create_transfer_creates_two_transactions_and_link`
  - Two accounts in same workspace.
  - Request `from_amount=100`, same currency.
  - Assert outflow amount `-100`, inflow amount `100`, both type `transfer`, and one `TransactionLink(relation_type='transfer_pair')` added.
- `test_create_transfer_rejects_same_account`
  - Expect `422`.
- `test_create_transfer_rejects_account_outside_workspace`
  - Expect `404`.
- `test_create_transfer_requires_destination_amount_for_cross_currency_without_rate_snapshot`
  - If `from_currency_code != to_currency_code` and no `to_amount`, expect `422`.
- `test_create_transfer_rolls_back_on_integrity_error`
  - Simulate commit failure and assert rollback.

Then implement transfer endpoint.

### Step 6 — Update/delete tests first

Add tests:

- `test_update_transaction_replaces_editable_fields`
  - Update description, notes, category, amount.
  - Assert fingerprint regenerated if amount/description/date changes.
- `test_update_transaction_rejects_deleted_transaction`
  - Existing transaction with `deleted_at` set or `status='deleted'` returns `404`.
- `test_update_transaction_replaces_splits_atomically`
  - Existing splits removed/replaced and new split validation applied.
- `test_update_transaction_rejects_split_sum_mismatch`.
- `test_soft_delete_transaction_sets_status_and_deleted_at`
  - Assert no physical delete call.
  - Assert `status='deleted'`, `deleted_at` set, commit called.
- `test_soft_delete_transfer_pair_deletes_both_sides` if choosing paired transfer deletion.
  - Recommended behavior: soft-delete both linked transactions for transfer consistency.

Then implement detail, update, and delete endpoints.

## 10. Acceptance criteria

Functional:

- Transactions can be created as expense/income/adjustment through `POST /workspaces/{workspace_id}/transactions`.
- Expense with non-negative amount is rejected before database commit.
- Income with non-positive amount is rejected before database commit.
- Category is optional.
- If category is provided, it must belong to the same workspace.
- If splits are provided:
  - Split categories must belong to the same workspace.
  - Split currency must match parent transaction currency.
  - Split amount sum must exactly equal parent transaction amount.
  - Split rows are persisted with the parent transaction.
- Transactions can be listed with default exclusion of soft-deleted rows.
- Transactions can be updated without changing immutable fields like type/status directly.
- Transactions can be soft-deleted only; no physical delete endpoint behavior.
- Transfers create two transaction rows and a `transfer_pair` link atomically.
- Cross-account transfer requires two different accounts in the same workspace.
- Cross-currency transfer stores snapshot fields supplied by caller; it does not fetch exchange rates.

Schema/migration:

- Alembic upgrade creates `transactions`, `transaction_splits`, and `transaction_links`.
- Alembic downgrade drops the new indexes/tables in dependency-safe order.
- Models are registered in `Base.metadata` via `backend/app/models/__init__.py`.
- Migration does not reference import tables that do not exist yet.
- Unique active fingerprint allows re-creating a similar transaction only after the old one has `deleted_at` set.

Testing/quality:

- Tests exist for expense, income, transfer, split validation, update, list, and soft delete.
- Tests follow existing `backend/tests/test_accounts_categories.py` style unless a real async DB fixture is introduced later.
- `ruff` passes.
- Relevant pytest suite passes.
- Alembic downgrade/upgrade path is verified.

## 11. Validation commands

Run from repo root unless command changes directory.

Pre-flight:

```bash
git status --short --branch
```

Narrow tests while developing:

```bash
cd backend
uv run pytest -q tests/test_transactions.py
```

Regression tests for adjacent patterns:

```bash
cd backend
uv run pytest -q tests/test_accounts_categories.py tests/test_transactions.py
```

Lint:

```bash
cd backend
uv run ruff check .
```

Full backend test pass:

```bash
cd backend
uv run pytest -q
```

Migration verification, with PostgreSQL available:

```bash
docker compose -f infra/docker-compose.yml up -d postgres
cd backend
uv run alembic downgrade base
uv run alembic upgrade head
```

Optional metadata smoke check if migration issues appear:

```bash
cd backend
uv run python -c "from app.db.base import Base; import app.models; print(sorted(Base.metadata.tables))"
```

## 12. Risks and implementation notes

- Existing tests use fake sessions, so query filtering details may be under-tested. Keep unit tests focused and add real DB integration tests in a later phase if needed.
- SQLAlchemy relationship loading can cause async serialization pitfalls if `TransactionRead.splits` accesses unloaded relationships after commit. Prefer explicit `selectinload(Transaction.splits)` for read/list/detail paths or build response objects deliberately.
- Updating splits by physical row deletion is acceptable for split rows because the soft-delete rule applies to transactions, not split details. If auditability becomes required, add split history later.
- Fingerprint generation is a minimal placeholder for the table constraint, not the duplicate-detection feature. Do not add fuzzy matching, duplicate candidates, or import row linkage in this phase.
- Partial unique indexes require PostgreSQL-specific `postgresql_where` in both model metadata and migration.
- Transfer deletion semantics can surprise users. Recommended MVP behavior is to soft-delete both sides of a transfer pair together; document this in tests and API behavior.

## 13. Recommended implementer assignment

Use one backend implementer for this entire Phase 4 slice because the same files and one migration chain are involved. Do not parallelize model/migration/API work across multiple agents unless using separate worktrees and strict file partitioning, because all tasks depend on `transaction.py`, schemas, router, and revision `0003`.

Suggested assignment prompt:

```markdown
You are the Implementer for `personal-budget-platform` Phase 4 transactions/splits.

Read first:
- `AGENTS.md`
- `.hermes/workflows/multi-agent-development.md`
- `.hermes/plans/2026-05-21_phase-4-transactions-splits.md`

Task:
Implement the backend transactions/splits/transfer slice exactly as planned. Use TDD. Stay narrow: no imports, budgets, auth implementation, frontend, or duplicate-detection service beyond minimal fingerprint generation.

Constraints:
- Do not touch unrelated files.
- Write failing tests first.
- Add Alembic migration and downgrade.
- Run the validation commands from the plan and report pass/fail.
- Return the standard handoff format from `AGENTS.md`.
```
