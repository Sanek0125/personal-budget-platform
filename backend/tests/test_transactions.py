from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, inspect
from sqlalchemy.exc import IntegrityError

from app.api.transactions import (
    create_transaction,
    create_transfer,
    delete_transaction,
    list_transactions,
    update_transaction,
)
from app.db.base import Base
from app.models import (
    Account,
    AuditLog,
    Category,
    Transaction,
    TransactionLink,
    TransactionSplit,
)
from app.schemas.transaction import (
    TransactionCreate,
    TransactionSplitCreate,
    TransactionUpdate,
    TransferCreate,
)


class _ScalarResult:
    def __init__(
        self, value: object | None = None, values: list[object] | None = None
    ) -> None:
        self._value = value
        self._values = values or ([] if value is None else [value])

    def scalar_one_or_none(self) -> object | None:
        return self._value

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[object]:
        return self._values


class _FakeAsyncSession:
    def __init__(
        self,
        *results: object | list[object] | None,
        commit_exception: Exception | None = None,
        flush_exception: Exception | None = None,
    ) -> None:
        self.results = list(results)
        self.commit_exception = commit_exception
        self.flush_exception = flush_exception
        self.added: list[object] = []
        self.added_all: list[object] = []
        self.deleted: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.flushed = False
        self.refreshed: list[object] = []
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        value = self.results.pop(0) if self.results else None
        if isinstance(value, list):
            return _ScalarResult(values=value)
        return _ScalarResult(value)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def add_all(self, objects: list[object]) -> None:
        self.added_all.extend(objects)

    async def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    async def flush(self) -> None:
        if self.flush_exception is not None:
            raise self.flush_exception
        self.flushed = True

    async def commit(self) -> None:
        if self.commit_exception is not None:
            raise self.commit_exception
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(
        self, obj: object, attribute_names: list[str] | None = None
    ) -> None:
        del attribute_names
        self.refreshed.append(obj)


def _account(workspace_id, account_id=None, currency_code="USD") -> Account:
    return Account(
        id=account_id or uuid4(),
        workspace_id=workspace_id,
        name="Cash",
        type="cash",
        currency_code=currency_code,
    )


def _category(workspace_id, category_id=None) -> Category:
    return Category(
        id=category_id or uuid4(),
        workspace_id=workspace_id,
        name="Food",
        type="expense",
    )


def _transaction(workspace_id, account_id=None, amount=Decimal("-10")) -> Transaction:
    return Transaction(
        workspace_id=workspace_id,
        account_id=account_id or uuid4(),
        type="expense" if amount < 0 else "income",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        amount=amount,
        currency_code="USD",
        description="Coffee",
        source="manual",
        fingerprint="fp",
    )


def test_transaction_models_are_registered_with_metadata() -> None:
    assert Transaction.__tablename__ == "transactions"
    assert TransactionSplit.__tablename__ == "transaction_splits"
    assert TransactionLink.__tablename__ == "transaction_links"
    assert {"transactions", "transaction_splits", "transaction_links"}.issubset(
        Base.metadata.tables
    )


def test_transaction_model_has_expected_constraints_and_indexes() -> None:
    table = Base.metadata.tables["transactions"]
    constraints = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {index.name: index for index in table.indexes if isinstance(index, Index)}
    link_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["transaction_links"].constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert {
        "ck_transactions_type",
        "ck_transactions_status",
        "ck_transactions_source",
        "ck_transactions_expense_negative",
        "ck_transactions_income_positive",
        "ck_transactions_transfer_nonzero",
    }.issubset(constraints)
    assert {
        "uq_transactions_active_fingerprint",
        "ix_transactions_workspace_occurred_at",
        "ix_transactions_account_occurred_at",
        "ix_transactions_category_id",
    }.issubset(indexes)
    assert indexes["uq_transactions_active_fingerprint"].unique is True
    assert "deleted_at IS NULL" in str(
        indexes["uq_transactions_active_fingerprint"].dialect_options["postgresql"][
            "where"
        ]
    )
    assert "uq_transaction_links_pair_type" in link_constraints


def test_transaction_relationship_annotations_are_configured() -> None:
    transaction_relationships = {rel.key for rel in inspect(Transaction).relationships}
    split_relationships = {rel.key for rel in inspect(TransactionSplit).relationships}

    assert {"workspace", "account", "user", "category", "currency", "splits"}.issubset(
        transaction_relationships
    )
    assert {"transaction", "category", "currency"}.issubset(split_relationships)


def test_transaction_schema_normalizes_currency_codes() -> None:
    payload = TransactionCreate(
        account_id=uuid4(),
        type="expense",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        amount=Decimal("-10"),
        currency_code="usd",
        original_currency_code="eur",
        base_currency_code="rub",
        description="Coffee",
    )

    assert payload.currency_code == "USD"
    assert payload.original_currency_code == "EUR"
    assert payload.base_currency_code == "RUB"


def test_transaction_schema_requires_expense_negative() -> None:
    try:
        TransactionCreate(
            account_id=uuid4(),
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("1"),
            currency_code="USD",
            description="Bad expense",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("expense amount must be negative")


def test_transaction_schema_requires_income_positive() -> None:
    try:
        TransactionCreate(
            account_id=uuid4(),
            type="income",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-1"),
            currency_code="USD",
            description="Bad income",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("income amount must be positive")


def test_transfer_schema_accepts_positive_from_amount_and_normalizes_codes() -> None:
    payload = TransferCreate(
        from_account_id=uuid4(),
        to_account_id=uuid4(),
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        from_amount=Decimal("100"),
        from_currency_code="usd",
        to_currency_code="eur",
        description="Move money",
    )

    assert payload.from_currency_code == "USD"
    assert payload.to_currency_code == "EUR"


def test_transfer_schema_rejects_non_positive_from_amount() -> None:
    try:
        TransferCreate(
            from_account_id=uuid4(),
            to_account_id=uuid4(),
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            from_amount=Decimal("0"),
            from_currency_code="USD",
            description="Bad transfer",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("transfer from_amount must be positive")


def test_split_schema_normalizes_currency_code() -> None:
    payload = TransactionSplitCreate(
        category_id=uuid4(), amount=Decimal("-10"), currency_code="usd"
    )
    assert payload.currency_code == "USD"


async def test_create_expense_transaction_creates_posted_manual_transaction() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(workspace_id, account)

    transaction = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account.id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-12.34"),
            currency_code="USD",
            description="Lunch",
        ),
        session,  # type: ignore[arg-type]
    )

    assert transaction in session.added
    assert any(isinstance(obj, AuditLog) for obj in session.added)
    assert session.flushed is True
    assert session.committed is True
    assert session.refreshed == [transaction]
    assert transaction.workspace_id == workspace_id
    assert transaction.status == "posted"
    assert transaction.source == "manual"
    assert transaction.fingerprint


async def test_create_income_transaction_with_optional_category() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    category = _category(workspace_id)
    session = _FakeAsyncSession(workspace_id, account, category)

    transaction = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account.id,
            type="income",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("100"),
            currency_code="USD",
            description="Salary",
            category_id=category.id,
        ),
        session,  # type: ignore[arg-type]
    )

    assert transaction.category_id == category.id


async def test_create_transaction_rejects_account_outside_workspace() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(workspace_id, None)

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=uuid4(),
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Account not found in this workspace"
    else:
        raise AssertionError("external account should be rejected")


async def test_create_transaction_translates_duplicate_fingerprint_to_conflict() -> (
    None
):
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        account,
        commit_exception=IntegrityError("statement", "params", Exception("uq")),
    )

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert session.rolled_back is True
    else:
        raise AssertionError("duplicate fingerprint should be translated")


async def test_list_transactions_excludes_deleted_by_default() -> None:
    workspace_id = uuid4()
    visible = _transaction(workspace_id)
    session = _FakeAsyncSession([visible])

    transactions = await list_transactions(workspace_id, session)  # type: ignore[arg-type]

    assert transactions == [visible]
    assert "deleted_at IS NULL" in str(session.statements[0])


async def test_create_transaction_with_valid_splits_adds_split_rows() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    category_a = _category(workspace_id)
    category_b = _category(workspace_id)
    session = _FakeAsyncSession(workspace_id, account, category_a, category_b)

    transaction = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account.id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-100"),
            currency_code="USD",
            description="Groceries",
            splits=[
                TransactionSplitCreate(
                    category_id=category_a.id,
                    amount=Decimal("-60"),
                    currency_code="USD",
                ),
                TransactionSplitCreate(
                    category_id=category_b.id,
                    amount=Decimal("-40"),
                    currency_code="USD",
                ),
            ],
        ),
        session,  # type: ignore[arg-type]
    )

    assert transaction in session.added
    assert len(session.added_all) == 2
    assert {split.transaction_id for split in session.added_all} == {transaction.id}


async def test_create_transaction_rejects_split_sum_mismatch() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    category = _category(workspace_id)
    session = _FakeAsyncSession(workspace_id, account, category)

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-100"),
                currency_code="USD",
                description="Groceries",
                splits=[
                    TransactionSplitCreate(
                        category_id=category.id,
                        amount=Decimal("-90"),
                        currency_code="USD",
                    )
                ],
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Split amounts must equal transaction amount"
    else:
        raise AssertionError("split sum mismatch should be rejected")


async def test_create_transaction_rejects_split_currency_mismatch() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(workspace_id, account)

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-100"),
                currency_code="USD",
                description="Groceries",
                splits=[
                    TransactionSplitCreate(
                        category_id=uuid4(), amount=Decimal("-100"), currency_code="EUR"
                    )
                ],
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Split currency must match transaction currency"
    else:
        raise AssertionError("split currency mismatch should be rejected")


async def test_create_transfer_creates_two_transactions_and_link() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id)
    to_account = _account(workspace_id)
    session = _FakeAsyncSession(workspace_id, from_account, to_account)

    transfer = await create_transfer(
        workspace_id,
        TransferCreate(
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            from_amount=Decimal("100"),
            from_currency_code="USD",
            description="Savings",
        ),
        session,  # type: ignore[arg-type]
    )

    assert transfer.outflow.amount == Decimal("-100")
    assert transfer.inflow.amount == Decimal("100")
    assert transfer.outflow.type == "transfer"
    assert transfer.inflow.type == "transfer"
    assert transfer.link_id
    assert len(session.added_all) == 3
    assert any(isinstance(obj, TransactionLink) for obj in session.added_all)


async def test_create_transfer_rejects_same_account() -> None:
    account_id = uuid4()
    try:
        await create_transfer(
            uuid4(),
            TransferCreate(
                from_account_id=account_id,
                to_account_id=account_id,
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                from_amount=Decimal("100"),
                from_currency_code="USD",
                description="Bad",
            ),
            _FakeAsyncSession(),  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("same-account transfer should be rejected")


async def test_create_transfer_requires_to_amount_for_cross_currency() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id, currency_code="USD")
    to_account = _account(workspace_id, currency_code="EUR")
    session = _FakeAsyncSession(workspace_id, from_account, to_account)

    try:
        await create_transfer(
            workspace_id,
            TransferCreate(
                from_account_id=from_account.id,
                to_account_id=to_account.id,
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                from_amount=Decimal("100"),
                from_currency_code="USD",
                to_currency_code="EUR",
                description="FX",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert (
            exc.detail
            == "Cross-currency transfers require to_amount or exchange snapshot"
        )
    else:
        raise AssertionError(
            "cross-currency transfer without amount or rate should be rejected"
        )


async def test_update_transaction_replaces_editable_fields_and_splits() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id)
    category = _category(workspace_id)
    old_split = TransactionSplit(
        transaction_id=existing.id,
        category_id=category.id,
        amount=Decimal("-10"),
        currency_code="USD",
    )
    existing.splits = [old_split]
    session = _FakeAsyncSession(existing, category, [old_split], category)

    updated = await update_transaction(
        workspace_id,
        existing.id,
        TransactionUpdate(
            description="Updated",
            amount=Decimal("-20"),
            category_id=category.id,
            splits=[
                TransactionSplitCreate(
                    category_id=category.id, amount=Decimal("-20"), currency_code="USD"
                )
            ],
        ),
        session,  # type: ignore[arg-type]
    )

    assert updated.description == "Updated"
    assert updated.amount == Decimal("-20")
    assert session.deleted == [old_split]
    assert len(session.added_all) == 1
    assert session.committed is True


async def test_update_transaction_rejects_deleted_transaction() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id)
    existing.status = "deleted"
    session = _FakeAsyncSession(existing)

    try:
        await update_transaction(
            workspace_id,
            existing.id,
            TransactionUpdate(description="Nope"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("deleted transaction update should be hidden")


async def test_soft_delete_transaction_sets_status_and_deleted_at() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id)
    session = _FakeAsyncSession(existing, None)

    await delete_transaction(workspace_id, existing.id, session)  # type: ignore[arg-type]

    assert existing.status == "deleted"
    assert existing.deleted_at is not None
    assert session.deleted == []
    assert session.committed is True



def test_transaction_schema_rejects_too_many_decimal_places() -> None:
    try:
        TransactionCreate(
            account_id=uuid4(),
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-1.1234567"),
            currency_code="USD",
            description="Too precise",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("money amount scale must be constrained to 6 decimals")


async def test_create_transaction_rejects_currency_outside_account_currency() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id, currency_code="USD")
    session = _FakeAsyncSession(workspace_id, account)

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="EUR",
                description="Wrong currency",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Transaction currency must match account currency"
    else:
        raise AssertionError("transaction currency must match account currency")


async def test_create_transaction_rejects_category_outside_workspace() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    category_id = uuid4()
    session = _FakeAsyncSession(workspace_id, account, None)

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
                category_id=category_id,
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Category not found in this workspace"
    else:
        raise AssertionError("external category should be rejected")


async def test_create_transaction_rejects_split_category_outside_workspace() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(workspace_id, account, None)

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-10"),
                currency_code="USD",
                description="Split",
                splits=[
                    TransactionSplitCreate(
                        category_id=uuid4(), amount=Decimal("-10"), currency_code="USD"
                    )
                ],
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Split category not found in this workspace"
    else:
        raise AssertionError("external split category should be rejected")


async def test_create_transfer_rejects_account_outside_workspace() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id)
    session = _FakeAsyncSession(workspace_id, from_account, None)

    try:
        await create_transfer(
            workspace_id,
            TransferCreate(
                from_account_id=from_account.id,
                to_account_id=uuid4(),
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                from_amount=Decimal("100"),
                from_currency_code="USD",
                description="Bad transfer",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Account not found in this workspace"
    else:
        raise AssertionError("external transfer account should be rejected")


async def test_create_transfer_rejects_currency_mismatch_with_accounts() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id, currency_code="USD")
    to_account = _account(workspace_id, currency_code="EUR")
    session = _FakeAsyncSession(workspace_id, from_account, to_account)

    try:
        await create_transfer(
            workspace_id,
            TransferCreate(
                from_account_id=from_account.id,
                to_account_id=to_account.id,
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                from_amount=Decimal("100"),
                from_currency_code="RUB",
                to_amount=Decimal("90"),
                to_currency_code="EUR",
                description="Bad FX",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == (
            "Transfer from_currency_code must match source account currency"
        )
    else:
        raise AssertionError("transfer currency must match account currency")


async def test_create_transfer_rolls_back_on_integrity_error() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id)
    to_account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        from_account,
        to_account,
        commit_exception=IntegrityError("statement", "params", Exception("uq")),
    )

    try:
        await create_transfer(
            workspace_id,
            TransferCreate(
                from_account_id=from_account.id,
                to_account_id=to_account.id,
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                from_amount=Decimal("100"),
                from_currency_code="USD",
                description="Duplicate transfer",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert session.rolled_back is True
    else:
        raise AssertionError("transfer integrity error should roll back")


async def test_update_transaction_rejects_split_sum_mismatch() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id)
    category = _category(workspace_id)
    session = _FakeAsyncSession(existing, [TransactionSplit()], category)

    try:
        await update_transaction(
            workspace_id,
            existing.id,
            TransactionUpdate(
                amount=Decimal("-20"),
                splits=[
                    TransactionSplitCreate(
                        category_id=category.id,
                        amount=Decimal("-10"),
                        currency_code="USD",
                    )
                ],
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Split amounts must equal transaction amount"
    else:
        raise AssertionError("update split sum mismatch should be rejected")


async def test_soft_delete_transfer_pair_deletes_both_sides() -> None:
    workspace_id = uuid4()
    outflow = _transaction(workspace_id, amount=Decimal("-100"))
    outflow.type = "transfer"
    inflow = _transaction(workspace_id, amount=Decimal("100"))
    inflow.type = "transfer"
    link = TransactionLink(
        workspace_id=workspace_id,
        transaction_id=outflow.id,
        linked_transaction_id=inflow.id,
        relation_type="transfer_pair",
    )
    session = _FakeAsyncSession(outflow, link, inflow)

    await delete_transaction(workspace_id, outflow.id, session)  # type: ignore[arg-type]

    assert outflow.status == "deleted"
    assert inflow.status == "deleted"
    assert outflow.deleted_at is not None
    assert inflow.deleted_at == outflow.deleted_at



async def test_create_transaction_translates_flush_duplicate_to_conflict() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        account,
        flush_exception=IntegrityError("statement", "params", Exception("uq")),
    )

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert session.rolled_back is True
    else:
        raise AssertionError("flush duplicate fingerprint should be translated")


async def test_update_transaction_rejects_currency_outside_account_currency() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id)
    account = _account(
        workspace_id, account_id=existing.account_id, currency_code="USD"
    )
    session = _FakeAsyncSession(existing, account)

    try:
        await update_transaction(
            workspace_id,
            existing.id,
            TransactionUpdate(currency_code="EUR"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Transaction currency must match account currency"
    else:
        raise AssertionError("updated transaction currency must match account")


async def test_update_rejects_amount_change_without_matching_splits() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id, amount=Decimal("-100"))
    category = _category(workspace_id)
    existing.splits = [
        TransactionSplit(
            transaction_id=existing.id,
            category_id=category.id,
            amount=Decimal("-100"),
            currency_code="USD",
        )
    ]
    session = _FakeAsyncSession(existing)

    try:
        await update_transaction(
            workspace_id,
            existing.id,
            TransactionUpdate(amount=Decimal("-120")),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Split amounts must equal transaction amount"
    else:
        raise AssertionError("existing splits must stay consistent on amount update")


async def test_create_transfer_derives_to_amount_from_exchange_rate_snapshot() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id, currency_code="USD")
    to_account = _account(workspace_id, currency_code="EUR")
    session = _FakeAsyncSession(workspace_id, from_account, to_account)

    transfer = await create_transfer(
        workspace_id,
        TransferCreate(
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            from_amount=Decimal("100"),
            from_currency_code="USD",
            to_currency_code="EUR",
            exchange_rate=Decimal("0.9"),
            description="FX",
        ),
        session,  # type: ignore[arg-type]
    )

    assert transfer.inflow.amount == Decimal("90.0")



async def test_update_transaction_rejects_direct_transfer_edit() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id, amount=Decimal("-100"))
    existing.type = "transfer"
    session = _FakeAsyncSession(existing)

    try:
        await update_transaction(
            workspace_id,
            existing.id,
            TransactionUpdate(description="Edited transfer"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Transfer transactions cannot be updated directly"
    else:
        raise AssertionError("direct transfer transaction edits should be rejected")


async def test_create_transaction_fingerprint_keeps_legacy_semantics() -> None:
    workspace_id = uuid4()
    account_id = uuid4()

    clean_session = _FakeAsyncSession(
        workspace_id, _account(workspace_id, account_id=account_id)
    )
    clean = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account_id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-12.00"),
            currency_code="USD",
            description="Coffee Shop",
        ),
        clean_session,  # type: ignore[arg-type]
    )

    same_amount_scale_session = _FakeAsyncSession(
        workspace_id, _account(workspace_id, account_id=account_id)
    )
    same_amount_scale = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account_id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-12.000000"),
            currency_code="USD",
            description="Coffee Shop",
        ),
        same_amount_scale_session,  # type: ignore[arg-type]
    )

    changed_description_session = _FakeAsyncSession(
        workspace_id, _account(workspace_id, account_id=account_id)
    )
    changed_description = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account_id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-12.00"),
            currency_code="USD",
            description="  coffee   SHOP ",
        ),
        changed_description_session,  # type: ignore[arg-type]
    )

    assert clean.fingerprint == same_amount_scale.fingerprint
    assert clean.fingerprint != changed_description.fingerprint


def _fingerprint_integrity_error() -> IntegrityError:
    """Build an IntegrityError whose orig names the fingerprint unique index."""
    return IntegrityError(
        "INSERT INTO transactions ...",
        "params",
        Exception(
            "duplicate key value violates unique constraint "
            '"uq_transactions_active_fingerprint"'
        ),
    )


async def test_create_transaction_names_fingerprint_index_in_conflict() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        account,
        commit_exception=_fingerprint_integrity_error(),
    )

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "fingerprint" in exc.detail
        assert session.rolled_back is True
    else:
        raise AssertionError("fingerprint index hit should produce a clear 409")


async def test_create_transaction_flush_names_fingerprint_index_in_conflict() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        account,
        flush_exception=_fingerprint_integrity_error(),
    )

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "fingerprint" in exc.detail
        assert session.rolled_back is True
    else:
        raise AssertionError("fingerprint index hit on flush should produce a 409")


async def test_update_transaction_names_fingerprint_index_in_conflict() -> None:
    workspace_id = uuid4()
    existing = _transaction(workspace_id)
    session = _FakeAsyncSession(
        existing,
        commit_exception=_fingerprint_integrity_error(),
    )

    try:
        await update_transaction(
            workspace_id,
            existing.id,
            TransactionUpdate(description="Updated"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "fingerprint" in exc.detail
        assert session.rolled_back is True
    else:
        raise AssertionError("fingerprint index hit on update should produce a 409")


async def test_create_transfer_names_fingerprint_index_in_conflict() -> None:
    workspace_id = uuid4()
    from_account = _account(workspace_id)
    to_account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        from_account,
        to_account,
        commit_exception=_fingerprint_integrity_error(),
    )

    try:
        await create_transfer(
            workspace_id,
            TransferCreate(
                from_account_id=from_account.id,
                to_account_id=to_account.id,
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                from_amount=Decimal("100"),
                from_currency_code="USD",
                description="Duplicate transfer",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "fingerprint" in exc.detail
        assert session.rolled_back is True
    else:
        raise AssertionError("fingerprint index hit on transfer should produce a 409")


async def test_integrity_error_without_fingerprint_index_stays_generic() -> None:
    workspace_id = uuid4()
    account = _account(workspace_id)
    session = _FakeAsyncSession(
        workspace_id,
        account,
        commit_exception=IntegrityError(
            "statement", "params", Exception("some other constraint")
        ),
    )

    try:
        await create_transaction(
            workspace_id,
            TransactionCreate(
                account_id=account.id,
                type="expense",
                occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
                amount=Decimal("-1"),
                currency_code="USD",
                description="Coffee",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "fingerprint" not in exc.detail
        assert session.rolled_back is True
    else:
        raise AssertionError("non-fingerprint integrity errors stay a generic 409")


async def test_distinct_descriptions_produce_distinct_fingerprints() -> None:
    workspace_id = uuid4()
    account_id = uuid4()

    first_session = _FakeAsyncSession(
        workspace_id, _account(workspace_id, account_id=account_id)
    )
    first = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account_id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-12.00"),
            currency_code="USD",
            description="Coffee",
        ),
        first_session,  # type: ignore[arg-type]
    )

    second_session = _FakeAsyncSession(
        workspace_id, _account(workspace_id, account_id=account_id)
    )
    second = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account_id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-12.00"),
            currency_code="USD",
            description="Tea",
        ),
        second_session,  # type: ignore[arg-type]
    )

    assert first.fingerprint != second.fingerprint
