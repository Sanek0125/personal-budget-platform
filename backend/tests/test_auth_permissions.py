from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.auth import (
    get_current_user_id,
    require_workspace_member,
    require_workspace_writer,
)
from app.main import app
from app.models import WorkspaceMember


class _Result:
    def __init__(self, value: object | None = None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeAsyncSession:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.statements: list[object] = []

    async def execute(self, statement: object) -> _Result:
        self.statements.append(statement)
        return _Result(self.value)


def test_current_user_id_requires_header() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing X-User-Id header"


async def test_require_workspace_member_returns_membership() -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    membership = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role="viewer",
    )
    session = _FakeAsyncSession(membership)

    result = await require_workspace_member(workspace_id, user_id, session)  # type: ignore[arg-type]

    assert result is membership
    assert len(session.statements) == 1


async def test_require_workspace_member_hides_non_member_workspace() -> None:
    session = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_member(uuid4(), uuid4(), session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Workspace not found"


async def test_require_workspace_writer_rejects_viewer() -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    session = _FakeAsyncSession(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            role="viewer",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_writer(workspace_id, user_id, session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Workspace write permission required"


def test_workspace_scoped_routes_require_dev_auth_header() -> None:
    client = TestClient(app)

    response = client.get(f"/workspaces/{uuid4()}/accounts")

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing X-User-Id header"}
