from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.auth import (
    authenticate_user,
    create_access_token,
    get_current_user_id,
    hash_password,
    login,
    register,
    verify_password,
)
from app.models import User
from app.schemas.auth import AuthLogin, AuthRegister


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


def _user(password: str = "correct-password", *, active: bool = True) -> User:
    return User(
        id=uuid4(),
        email="vasily@example.com",
        password_hash=hash_password(password),
        display_name="Василий",
        telegram_id=None,
        is_active=active,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_password_hashes_are_salted_and_verifiable() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second
    assert verify_password("correct horse battery staple", first) is True
    assert verify_password("wrong", first) is False


def test_access_token_round_trips_authenticated_user() -> None:
    user_id = uuid4()
    token = create_access_token(user_id, expires_delta=timedelta(minutes=5))

    assert token.startswith("v1.")


async def test_current_user_id_accepts_bearer_token_for_active_user() -> None:
    user = _user()
    session = _FakeAsyncSession(user)
    token = create_access_token(user.id, expires_delta=timedelta(minutes=5))

    result = await get_current_user_id(
        authorization=f"Bearer {token}",
        x_user_id=None,
        session=session,  # type: ignore[arg-type]
    )

    assert result == user.id
    assert len(session.statements) == 1


async def test_current_user_id_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(
            authorization=None,
            x_user_id=None,
            session=_FakeAsyncSession(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


async def test_current_user_id_rejects_invalid_bearer_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(
            authorization="Bearer not-a-valid-token",
            x_user_id=None,
            session=_FakeAsyncSession(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid access token"


async def test_current_user_id_keeps_dev_header_fallback() -> None:
    dev_user_id = uuid4()

    result = await get_current_user_id(
        authorization=None,
        x_user_id=dev_user_id,
        session=_FakeAsyncSession(),  # type: ignore[arg-type]
    )

    assert result == dev_user_id


async def test_authenticate_user_returns_active_user_for_valid_credentials() -> None:
    user = _user()
    session = _FakeAsyncSession(user)

    result = await authenticate_user(
        "  VASILY@EXAMPLE.COM  ",
        "correct-password",
        session,  # type: ignore[arg-type]
    )

    assert result is user


async def test_authenticate_user_rejects_wrong_password() -> None:
    session = _FakeAsyncSession(_user())

    with pytest.raises(HTTPException) as exc_info:
        await authenticate_user("vasily@example.com", "wrong-password", session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"


async def test_register_creates_user_with_password_hash_and_returns_token() -> None:
    session = _FakeAsyncSession()

    response = await register(
        AuthRegister(
            email="  VASILY@EXAMPLE.COM  ",
            password="correct-password",
            display_name="  Василий  ",
        ),
        session,  # type: ignore[arg-type]
    )

    assert response.token_type == "bearer"
    assert response.access_token.startswith("v1.")
    assert response.user.email == "vasily@example.com"
    assert response.user.display_name == "Василий"
    assert session.committed is True
    created_user = session.added[0]
    assert isinstance(created_user, User)
    assert created_user.email == "vasily@example.com"
    assert created_user.password_hash is not None
    assert created_user.password_hash != "correct-password"
    assert verify_password("correct-password", created_user.password_hash) is True


async def test_register_rolls_back_duplicate_email() -> None:
    session = _FakeAsyncSession(
        commit_error=IntegrityError("insert", {}, Exception("duplicate"))
    )

    with pytest.raises(HTTPException) as exc_info:
        await register(
            AuthRegister(
                email="vasily@example.com",
                password="correct-password",
                display_name="Василий",
            ),
            session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unable to register user"
    assert session.rolled_back is True


async def test_login_returns_token_for_valid_credentials() -> None:
    user = _user()
    session = _FakeAsyncSession(user)

    response = await login(
        AuthLogin(email="vasily@example.com", password="correct-password"),
        session,  # type: ignore[arg-type]
    )

    assert response.user.id == user.id
    assert response.token_type == "bearer"
    assert response.access_token.startswith("v1.")
