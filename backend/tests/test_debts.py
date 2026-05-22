from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, inspect

from app.api.debts import create_debt, create_debt_payment, get_debt_summary, list_debts
from app.db.base import Base
from app.models import Contact, Debt, DebtPayment, Transaction
from app.schemas.debt import DebtCreate, DebtPaymentCreate
from app.services.debts import calculate_debt_summary


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

    def unique(self) -> "_ScalarResult":
        return self


class _FakeAsyncSession:
    def __init__(self, *results: object | list[object] | None) -> None:
        self.results = list(results)
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False
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

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(
        self, obj: object, attribute_names: list[str] | None = None
    ) -> None:
        del attribute_names
        self.refreshed.append(obj)


def _contact(workspace_id, contact_id=None, display_name="Alex") -> Contact:
    return Contact(
        id=contact_id or uuid4(),
        workspace_id=workspace_id,
        display_name=display_name,
    )


def _debt(
    workspace_id,
    direction="they_owe_me",
    principal="100",
    currency_code="USD",
    status="open",
) -> Debt:
    debt = Debt(
        id=uuid4(),
        workspace_id=workspace_id,
        contact_id=uuid4(),
        direction=direction,
        status=status,
        principal_amount=Decimal(principal),
        currency_code=currency_code,
        description="Loan",
        opened_at=datetime(2026, 5, 22, tzinfo=UTC),
    )
    debt.payments = []
    return debt


def _payment(debt_id, amount="25", currency_code="USD") -> DebtPayment:
    return DebtPayment(
        id=uuid4(),
        debt_id=debt_id,
        amount=Decimal(amount),
        currency_code=currency_code,
        paid_at=datetime(2026, 5, 22, tzinfo=UTC),
    )


def _transaction(
    workspace_id, amount=Decimal("-100"), currency_code="USD"
) -> Transaction:
    return Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=uuid4(),
        type="expense" if amount < 0 else "income",
        status="posted",
        occurred_at=datetime(2026, 5, 22, tzinfo=UTC),
        amount=amount,
        currency_code=currency_code,
        description="Source",
        source="manual",
        fingerprint="fp",
    )


def test_debt_models_are_registered_with_metadata() -> None:
    assert Contact.__tablename__ == "contacts"
    assert Debt.__tablename__ == "debts"
    assert DebtPayment.__tablename__ == "debt_payments"
    assert {"contacts", "debts", "debt_payments"}.issubset(Base.metadata.tables)


def test_debt_model_has_expected_constraints_and_indexes() -> None:
    contacts = Base.metadata.tables["contacts"]
    debts = Base.metadata.tables["debts"]
    payments = Base.metadata.tables["debt_payments"]
    checks = {
        constraint.name
        for table in (debts, payments)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name
        for table in (contacts, debts, payments)
        for index in table.indexes
        if isinstance(index, Index)
    }

    assert {
        "ck_debts_direction",
        "ck_debts_status",
        "ck_debts_principal_amount_positive",
        "ck_debt_payments_amount_positive",
    }.issubset(checks)
    assert {
        "ix_contacts_workspace_display_name",
        "ix_debts_workspace_status",
        "ix_debts_contact_id",
        "ix_debt_payments_debt_id",
    }.issubset(indexes)


def test_debt_relationship_annotations_are_configured() -> None:
    contact_relationships = {rel.key for rel in inspect(Contact).relationships}
    debt_relationships = {rel.key for rel in inspect(Debt).relationships}
    payment_relationships = {rel.key for rel in inspect(DebtPayment).relationships}

    assert {"workspace", "debts"}.issubset(contact_relationships)
    assert {
        "workspace",
        "contact",
        "currency",
        "payments",
        "source_transaction",
    }.issubset(debt_relationships)
    assert {"debt", "currency", "transaction"}.issubset(payment_relationships)


def test_debt_schema_normalizes_currency_and_requires_positive_principal() -> None:
    payload = DebtCreate(
        contact_name="Alex",
        direction="they_owe_me",
        principal_amount=Decimal("100"),
        currency_code="usd",
        description="Loan",
    )

    assert payload.currency_code == "USD"

    try:
        DebtCreate(
            contact_name="Alex",
            direction="they_owe_me",
            principal_amount=Decimal("0"),
            currency_code="USD",
            description="Bad",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("principal_amount must be positive")


async def test_create_they_owe_me_debt_creates_contact_and_debt() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(workspace_id)

    debt = await create_debt(
        workspace_id,
        DebtCreate(
            contact_name="Alex",
            direction="they_owe_me",
            principal_amount=Decimal("100"),
            currency_code="USD",
            description="Lunch loan",
        ),
        session,  # type: ignore[arg-type]
    )

    assert debt.workspace_id == workspace_id
    assert debt.direction == "they_owe_me"
    assert debt.status == "open"
    assert debt.principal_amount == Decimal("100")
    assert any(isinstance(obj, Contact) for obj in session.added)
    assert debt in session.added
    assert session.committed is True


async def test_create_i_owe_them_debt_uses_existing_contact() -> None:
    workspace_id = uuid4()
    contact = _contact(workspace_id)
    session = _FakeAsyncSession(workspace_id, contact)

    debt = await create_debt(
        workspace_id,
        DebtCreate(
            contact_id=contact.id,
            direction="i_owe_them",
            principal_amount=Decimal("75"),
            currency_code="USD",
            description="Borrowed cash",
        ),
        session,  # type: ignore[arg-type]
    )

    assert debt.contact_id == contact.id
    assert debt.direction == "i_owe_them"
    assert session.added == [debt]


async def test_partial_repayment_marks_debt_partially_paid() -> None:
    workspace_id = uuid4()
    debt = _debt(workspace_id, principal="100")
    session = _FakeAsyncSession(debt)

    payment = await create_debt_payment(
        workspace_id,
        debt.id,
        DebtPaymentCreate(amount=Decimal("40"), currency_code="USD"),
        session,  # type: ignore[arg-type]
    )

    assert payment.amount == Decimal("40")
    assert debt.status == "partially_paid"
    assert debt.closed_at is None
    assert payment in session.added
    assert session.committed is True


async def test_full_repayment_closes_debt() -> None:
    workspace_id = uuid4()
    debt = _debt(workspace_id, principal="100")
    debt.payments = [_payment(debt.id, "40")]
    session = _FakeAsyncSession(debt)

    await create_debt_payment(
        workspace_id,
        debt.id,
        DebtPaymentCreate(amount=Decimal("60"), currency_code="USD"),
        session,  # type: ignore[arg-type]
    )

    assert debt.status == "paid"
    assert debt.closed_at is not None


async def test_overpayment_rejected() -> None:
    workspace_id = uuid4()
    debt = _debt(workspace_id, principal="100")
    debt.payments = [_payment(debt.id, "90")]
    session = _FakeAsyncSession(debt)

    try:
        await create_debt_payment(
            workspace_id,
            debt.id,
            DebtPaymentCreate(amount=Decimal("11"), currency_code="USD"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Debt payment would exceed principal amount"
    else:
        raise AssertionError("overpayment should be rejected")


async def test_payment_currency_mismatch_rejected() -> None:
    workspace_id = uuid4()
    debt = _debt(workspace_id, currency_code="USD")
    session = _FakeAsyncSession(debt)

    try:
        await create_debt_payment(
            workspace_id,
            debt.id,
            DebtPaymentCreate(amount=Decimal("10"), currency_code="EUR"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Debt payment currency must match debt currency"
    else:
        raise AssertionError("currency mismatch should be rejected")


async def test_payment_transaction_validates_workspace_and_currency() -> None:
    workspace_id = uuid4()
    debt = _debt(workspace_id, principal="100", currency_code="USD")
    transaction = _transaction(workspace_id, currency_code="USD")
    session = _FakeAsyncSession(debt, transaction)

    payment = await create_debt_payment(
        workspace_id,
        debt.id,
        DebtPaymentCreate(
            amount=Decimal("10"),
            currency_code="USD",
            transaction_id=transaction.id,
        ),
        session,  # type: ignore[arg-type]
    )

    assert payment.transaction_id == transaction.id

    other_workspace_id = uuid4()
    foreign_transaction = _transaction(other_workspace_id, currency_code="USD")
    session = _FakeAsyncSession(debt, foreign_transaction)
    try:
        await create_debt_payment(
            workspace_id,
            debt.id,
            DebtPaymentCreate(
                amount=Decimal("10"),
                currency_code="USD",
                transaction_id=foreign_transaction.id,
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Payment transaction not found in this workspace"
    else:
        raise AssertionError("foreign payment transaction should be rejected")

    currency_mismatch = _transaction(workspace_id, currency_code="EUR")
    session = _FakeAsyncSession(debt, currency_mismatch)
    try:
        await create_debt_payment(
            workspace_id,
            debt.id,
            DebtPaymentCreate(
                amount=Decimal("10"),
                currency_code="USD",
                transaction_id=currency_mismatch.id,
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Payment transaction currency must match debt currency"
    else:
        raise AssertionError("payment transaction currency mismatch should be rejected")


async def test_debt_created_from_transaction_validates_workspace_and_currency() -> None:
    workspace_id = uuid4()
    transaction = _transaction(workspace_id, currency_code="USD")
    session = _FakeAsyncSession(workspace_id, transaction)

    debt = await create_debt(
        workspace_id,
        DebtCreate(
            contact_name="Alex",
            direction="they_owe_me",
            principal_amount=Decimal("100"),
            currency_code="USD",
            description="From tx",
            source_transaction_id=transaction.id,
        ),
        session,  # type: ignore[arg-type]
    )

    assert debt.source_transaction_id == transaction.id

    other_workspace_id = uuid4()
    foreign_transaction = _transaction(other_workspace_id, currency_code="USD")
    session = _FakeAsyncSession(workspace_id, foreign_transaction)
    try:
        await create_debt(
            workspace_id,
            DebtCreate(
                contact_name="Alex",
                direction="they_owe_me",
                principal_amount=Decimal("100"),
                currency_code="USD",
                description="Bad tx",
                source_transaction_id=foreign_transaction.id,
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Source transaction not found in this workspace"
    else:
        raise AssertionError("foreign source transaction should be rejected")


async def test_source_transaction_currency_mismatch_rejected() -> None:
    workspace_id = uuid4()
    transaction = _transaction(workspace_id, currency_code="EUR")
    session = _FakeAsyncSession(workspace_id, transaction)

    try:
        await create_debt(
            workspace_id,
            DebtCreate(
                contact_name="Alex",
                direction="they_owe_me",
                principal_amount=Decimal("100"),
                currency_code="USD",
                description="Bad tx currency",
                source_transaction_id=transaction.id,
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Source transaction currency must match debt currency"
    else:
        raise AssertionError("source currency mismatch should be rejected")


def test_summary_totals_by_direction_and_currency() -> None:
    workspace_id = uuid4()
    they = _debt(
        workspace_id, direction="they_owe_me", principal="100", currency_code="USD"
    )
    they.payments = [_payment(they.id, "25")]
    owe = _debt(
        workspace_id, direction="i_owe_them", principal="50", currency_code="USD"
    )
    paid = _debt(workspace_id, direction="they_owe_me", principal="10", status="paid")
    paid.payments = [_payment(paid.id, "10")]

    summary = calculate_debt_summary([they, owe, paid])

    assert summary.totals[0].direction == "they_owe_me"
    assert summary.totals[0].currency_code == "USD"
    assert summary.totals[0].principal_amount == Decimal("100")
    assert summary.totals[0].paid_amount == Decimal("25")
    assert summary.totals[0].remaining_amount == Decimal("75")
    assert summary.totals[1].direction == "i_owe_them"
    assert summary.totals[1].remaining_amount == Decimal("50")


async def test_list_debts_and_summary_are_workspace_scoped() -> None:
    workspace_id = uuid4()
    debts = [_debt(workspace_id)]
    session = _FakeAsyncSession(debts, debts)

    assert await list_debts(workspace_id, session) == debts  # type: ignore[arg-type]
    summary = await get_debt_summary(workspace_id, session)  # type: ignore[arg-type]

    assert summary.workspace_id == workspace_id
    assert summary.totals[0].remaining_amount == Decimal("100")
