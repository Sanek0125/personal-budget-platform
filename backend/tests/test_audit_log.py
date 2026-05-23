from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index

from app.api.transactions import create_transaction, delete_transaction
from app.db.base import Base
from app.models import Account, AuditLog, Transaction
from app.schemas.transaction import TransactionCreate
from app.services.audit import ensure_audit_entity_id, record_audit_event


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
    def __init__(self, *results: object | list[object] | None) -> None:
        self.results = list(results)
        self.added: list[object] = []
        self.added_all: list[object] = []
        self.committed = False
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

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

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


def _transaction(workspace_id, account_id=None) -> Transaction:
    return Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=account_id or uuid4(),
        type="expense",
        status="posted",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        amount=Decimal("-10"),
        currency_code="USD",
        description="Coffee",
        source="manual",
        fingerprint="fp",
    )


def test_audit_log_model_is_registered_with_metadata() -> None:
    assert AuditLog.__tablename__ == "audit_log"
    assert "audit_log" in Base.metadata.tables


def test_audit_log_model_has_expected_constraints_and_indexes() -> None:
    table = Base.metadata.tables["audit_log"]
    constraints = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {index.name for index in table.indexes if isinstance(index, Index)}

    assert "ck_audit_log_action" in constraints
    assert "ix_audit_log_workspace_created_at" in indexes
    assert "ix_audit_log_entity" in indexes


def test_record_audit_event_adds_entry_without_committing() -> None:
    session = _FakeAsyncSession()
    workspace_id = uuid4()
    user_id = uuid4()
    entity_id = uuid4()

    entry = record_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        entity_type="transaction",
        entity_id=entity_id,
        action="create",
        old_data=None,
        new_data={"amount": "-10.000000"},
    )

    assert entry in session.added
    assert isinstance(entry, AuditLog)
    assert entry.workspace_id == workspace_id
    assert entry.user_id == user_id
    assert entry.entity_type == "transaction"
    assert entry.entity_id == entity_id
    assert entry.action == "create"
    assert entry.old_data is None
    assert entry.new_data == {"amount": "-10.000000"}
    assert session.committed is False


def test_ensure_audit_entity_id_assigns_id_before_flush() -> None:
    transaction = Transaction(
        workspace_id=uuid4(),
        account_id=uuid4(),
        type="expense",
        status="posted",
        occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
        amount=Decimal("-10"),
        currency_code="USD",
        source="manual",
        fingerprint="fp",
    )

    entity_id = ensure_audit_entity_id(transaction)

    assert transaction.id == entity_id
    assert entity_id is not None


async def test_create_transaction_adds_audit_log_entry() -> None:
    workspace_id = uuid4()
    account_id = uuid4()
    session = _FakeAsyncSession(workspace_id, _account(workspace_id, account_id))

    transaction = await create_transaction(
        workspace_id,
        TransactionCreate(
            account_id=account_id,
            type="expense",
            occurred_at=datetime(2026, 5, 21, tzinfo=UTC),
            amount=Decimal("-10"),
            currency_code="USD",
            description="Coffee",
        ),
        session,
    )

    audit_entries = [obj for obj in session.added if isinstance(obj, AuditLog)]
    assert len(audit_entries) == 1
    audit = audit_entries[0]
    assert audit.workspace_id == workspace_id
    assert audit.entity_type == "transaction"
    assert audit.entity_id == transaction.id
    assert audit.action == "create"
    assert audit.new_data["amount"] == "-10.000000"


async def test_delete_transaction_adds_audit_log_entry() -> None:
    workspace_id = uuid4()
    transaction = _transaction(workspace_id)
    session = _FakeAsyncSession(transaction, None)

    await delete_transaction(workspace_id, transaction.id, session)

    audit_entries = [obj for obj in session.added if isinstance(obj, AuditLog)]
    assert len(audit_entries) == 1
    audit = audit_entries[0]
    assert audit.workspace_id == workspace_id
    assert audit.entity_type == "transaction"
    assert audit.entity_id == transaction.id
    assert audit.action == "delete"
    assert audit.old_data["status"] == "posted"
    assert audit.new_data["status"] == "deleted"
