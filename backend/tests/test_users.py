from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.users import create_user, get_user, list_users
from app.models import User
from app.schemas.user import UserCreate


class _ScalarResult:
    def __init__(self, values: object | list[object] | None = None) -> None:
        if isinstance(values, list):
            self._values = values
            self._single = values[0] if values else None
        else:
            self._values = [] if values is None else [values]
            self._single = values

    def scalar_one_or_none(self) -> object | None:
        return self._single

    def all(self) -> list[object]:
        return self._values


class _Result:
    def __init__(self, values: object | list[object] | None = None) -> None:
        self._values = values

    def scalar_one_or_none(self) -> object | None:
        return _ScalarResult(self._values).scalar_one_or_none()

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._values)


class _FakeAsyncSession:
    def __init__(
        self,
        *results: object | list[object] | None,
        commit_error: Exception | None = None,
    ) -> None:
        self.results = list(results)
        self.commit_error = commit_error
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.refreshed: object | None = None
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _Result:
        self.statements.append(statement)
        value = self.results.pop(0) if self.results else None
        return _Result(value)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: object) -> None:
        self.refreshed = obj


def _user() -> User:
    return User(
        id=uuid4(),
        email="vasily@example.com",
        display_name="Василий",
        telegram_id=None,
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_user_create_schema_normalizes_email_and_display_name() -> None:
    payload = UserCreate(email="  VASILY@EXAMPLE.COM  ", display_name="  Василий  ")

    assert payload.email == "vasily@example.com"
    assert payload.display_name == "Василий"


@pytest.mark.parametrize("blank_name", ["", "   ", "\n\t"])
def test_user_create_schema_rejects_blank_display_name(blank_name: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="user@example.com", display_name=blank_name)


async def test_create_user_persists_user() -> None:
    session = _FakeAsyncSession()

    user = await create_user(
        UserCreate(email="  VASILY@EXAMPLE.COM  ", display_name="  Василий  "),
        session,  # type: ignore[arg-type]
    )

    assert isinstance(user, User)
    assert user.email == "vasily@example.com"
    assert user.display_name == "Василий"
    assert user.is_active is True
    assert session.added == [user]
    assert session.committed is True
    assert session.refreshed is user


async def test_create_user_rolls_back_duplicate_email() -> None:
    session = _FakeAsyncSession(
        commit_error=IntegrityError("insert", {}, Exception("duplicate"))
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_user(
            UserCreate(email="vasily@example.com", display_name="Василий"),
            session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unable to create user"
    assert session.rolled_back is True


async def test_get_user_returns_404_when_missing() -> None:
    session = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await get_user(uuid4(), session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


async def test_get_user_returns_user() -> None:
    user = _user()
    session = _FakeAsyncSession(user)

    result = await get_user(user.id, session)  # type: ignore[arg-type]

    assert result is user
    assert len(session.statements) == 1


async def test_list_users_filters_by_normalized_email() -> None:
    user = _user()
    session = _FakeAsyncSession([user])

    result = await list_users(session, email="  VASILY@EXAMPLE.COM  ")  # type: ignore[arg-type]

    assert result == [user]
    assert len(session.statements) == 1
