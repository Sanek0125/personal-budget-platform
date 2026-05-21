from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, inspect
from sqlalchemy.exc import IntegrityError

from app.api.accounts import create_account
from app.api.categories import create_category
from app.db.base import Base
from app.models import Account, Category
from app.schemas.account import AccountCreate
from app.schemas.category import CategoryCreate


class _ScalarResult:
    def __init__(self, value: object | None = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeAsyncSession:
    def __init__(
        self,
        *results: object | None,
        commit_exception: Exception | None = None,
    ) -> None:
        self.results = list(results)
        self.commit_exception = commit_exception
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.refreshed: object | None = None
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        value = self.results.pop(0) if self.results else None
        return _ScalarResult(value)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        if self.commit_exception is not None:
            raise self.commit_exception
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: object) -> None:
        self.refreshed = obj


def test_accounts_and_categories_models_are_registered_with_metadata() -> None:
    assert Account.__tablename__ == "accounts"
    assert Category.__tablename__ == "categories"
    assert {"accounts", "categories"}.issubset(Base.metadata.tables)


def test_account_schema_supports_personal_and_shared_accounts() -> None:
    owner_user_id = uuid4()

    personal = AccountCreate(
        owner_user_id=owner_user_id,
        name="Tinkoff Black",
        type="bank_card",
        currency_code="rub",
        opening_balance=Decimal("-1000.50"),
    )
    shared = AccountCreate(name="Family Cash", type="cash", currency_code="USD")

    assert personal.owner_user_id == owner_user_id
    assert personal.currency_code == "RUB"
    assert personal.opening_balance == Decimal("-1000.50")
    assert shared.owner_user_id is None
    assert shared.opening_balance == Decimal("0")


async def test_create_account_creates_personal_account() -> None:
    workspace_id = uuid4()
    owner_user_id = uuid4()
    session = _FakeAsyncSession(workspace_id, owner_user_id)

    account = await create_account(
        workspace_id,
        AccountCreate(
            owner_user_id=owner_user_id,
            name="Travel Card",
            type="bank_card",
            currency_code="EUR",
        ),
        session,  # type: ignore[arg-type]
    )

    assert session.added == [account]
    assert session.committed is True
    assert session.refreshed is account
    assert len(session.statements) == 2
    assert account.workspace_id == workspace_id
    assert account.owner_user_id == owner_user_id


async def test_create_account_creates_shared_account() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(workspace_id)

    account = await create_account(
        workspace_id,
        AccountCreate(name="Shared Cash", type="cash", currency_code="USD"),
        session,  # type: ignore[arg-type]
    )

    assert session.added == [account]
    assert account.workspace_id == workspace_id
    assert account.owner_user_id is None


async def test_create_account_translates_integrity_errors() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(
        workspace_id,
        commit_exception=IntegrityError("statement", "params", Exception("fk")),
    )

    try:
        await create_account(
            workspace_id,
            AccountCreate(name="Unknown Currency", type="cash", currency_code="ZZZ"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Unknown currency or owner for account"
        assert session.rolled_back is True
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("integrity errors should be translated to 422")


async def test_create_account_rejects_owner_outside_workspace() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(workspace_id, None)

    try:
        await create_account(
            workspace_id,
            AccountCreate(
                owner_user_id=uuid4(),
                name="External Owner",
                type="cash",
                currency_code="USD",
            ),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "Account owner must be a workspace member"
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("external owner should be rejected")


def test_category_model_supports_nested_categories() -> None:
    workspace_id = uuid4()
    parent_id = uuid4()

    category = Category(
        workspace_id=workspace_id,
        parent_id=parent_id,
        name="Coffee",
        type="expense",
    )

    assert category.workspace_id == workspace_id
    assert category.parent_id == parent_id
    assert category.name == "Coffee"


def test_category_duplicate_name_constraints_cover_root_and_nested_categories() -> None:
    table = Base.metadata.tables["categories"]
    unique_constraints = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    unique_indexes = {
        index.name: index
        for index in table.indexes
        if isinstance(index, Index) and index.unique
    }

    assert "uq_categories_workspace_parent_name" in unique_constraints
    assert "uq_categories_workspace_root_name" in unique_indexes
    assert "parent_id IS NULL" in str(
        unique_indexes["uq_categories_workspace_root_name"].dialect_options[
            "postgresql"
        ]["where"]
    )


async def test_create_category_creates_nested_category_with_valid_parent() -> None:
    workspace_id = uuid4()
    parent = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        parent_id=None,
        name="Food",
        type="expense",
    )
    session = _FakeAsyncSession(workspace_id, parent, None)

    category = await create_category(
        workspace_id,
        CategoryCreate(parent_id=parent.id, name="Coffee", type="expense"),
        session,  # type: ignore[arg-type]
    )

    assert len(session.statements) == 3
    assert session.added == [category]
    assert session.committed is True
    assert session.refreshed is category
    assert category.workspace_id == workspace_id
    assert category.parent_id == parent.id


async def test_create_category_rejects_parent_from_another_workspace() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(workspace_id, None)

    try:
        await create_category(
            workspace_id,
            CategoryCreate(parent_id=uuid4(), name="Coffee", type="expense"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Parent category not found in this workspace"
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("cross-workspace parent should be rejected")


async def test_create_category_rejects_duplicate_name_under_same_parent() -> None:
    workspace_id = uuid4()
    existing = Category(
        workspace_id=workspace_id,
        parent_id=None,
        name="Food",
        type="expense",
    )
    session = _FakeAsyncSession(workspace_id, existing)

    try:
        await create_category(
            workspace_id,
            CategoryCreate(name="Food", type="expense"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("duplicate category should be rejected")


async def test_create_category_rolls_back_integrity_errors() -> None:
    workspace_id = uuid4()
    session = _FakeAsyncSession(
        workspace_id,
        None,
        commit_exception=IntegrityError("statement", "params", Exception("uq")),
    )

    try:
        await create_category(
            workspace_id,
            CategoryCreate(name="Food", type="expense"),
            session,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert session.rolled_back is True
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("integrity errors should roll back")


def test_accounts_and_categories_have_expected_check_constraints_and_indexes() -> None:
    account_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["accounts"].constraints
        if isinstance(constraint, CheckConstraint)
    }
    category_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["categories"].constraints
        if isinstance(constraint, CheckConstraint)
    }
    account_indexes = {index.name for index in Base.metadata.tables["accounts"].indexes}
    category_indexes = {
        index.name for index in Base.metadata.tables["categories"].indexes
    }

    assert "ck_accounts_type" in account_constraints
    assert "ck_categories_type" in category_constraints
    assert {"ix_accounts_workspace_id", "ix_accounts_owner_user_id"}.issubset(
        account_indexes
    )
    assert {"ix_categories_workspace_id", "ix_categories_parent_id"}.issubset(
        category_indexes
    )


def test_account_category_relationship_annotations_are_configured() -> None:
    account_relationships = {rel.key for rel in inspect(Account).relationships}
    category_relationships = {rel.key for rel in inspect(Category).relationships}

    assert {"workspace", "owner", "currency"}.issubset(account_relationships)
    assert {"workspace", "parent"}.issubset(category_relationships)
