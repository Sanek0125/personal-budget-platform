from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.workspaces import (
    add_workspace_member,
    create_workspace,
    get_workspace,
    list_workspace_members,
    list_workspaces,
)
from app.models import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceMemberCreate


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


def _workspace() -> Workspace:
    return Workspace(
        id=uuid4(),
        name="Family",
        kind="family",
        base_currency_code="USD",
        owner_user_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_workspace_schema_normalizes_currency_and_trims_name() -> None:
    owner_user_id = uuid4()

    payload = WorkspaceCreate(
        name="  Family Budget  ",
        kind="family",
        base_currency_code=" usd ",
        owner_user_id=owner_user_id,
    )

    assert payload.name == "Family Budget"
    assert payload.base_currency_code == "USD"


@pytest.mark.parametrize("blank_name", ["", "   ", "\t\n"])
def test_workspace_schema_rejects_blank_names(blank_name: str) -> None:
    with pytest.raises(ValidationError):
        WorkspaceCreate(
            name=blank_name,
            kind="personal",
            base_currency_code="USD",
            owner_user_id=uuid4(),
        )


@pytest.mark.parametrize("bad_currency", [None, 123])
def test_workspace_schema_rejects_non_string_currency_codes(
    bad_currency: object,
) -> None:
    with pytest.raises(ValidationError):
        WorkspaceCreate(
            name="Personal",
            kind="personal",
            base_currency_code=bad_currency,  # type: ignore[arg-type]
            owner_user_id=uuid4(),
        )


async def test_create_workspace_creates_owner_membership() -> None:
    owner_user_id = uuid4()
    session = _FakeAsyncSession(owner_user_id, "USD")

    workspace = await create_workspace(
        WorkspaceCreate(
            name="Personal",
            kind="personal",
            base_currency_code="usd",
            owner_user_id=owner_user_id,
        ),
        session,  # type: ignore[arg-type]
    )

    assert isinstance(workspace, Workspace)
    assert workspace.name == "Personal"
    assert workspace.base_currency_code == "USD"
    assert workspace.owner_user_id == owner_user_id
    assert len(session.added) == 2
    assert session.added[0] is workspace
    membership = session.added[1]
    assert isinstance(membership, WorkspaceMember)
    assert membership.workspace is workspace
    assert membership.user_id == owner_user_id
    assert membership.role == "owner"
    assert session.committed is True
    assert session.refreshed is workspace


async def test_create_workspace_returns_404_when_owner_missing() -> None:
    session = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await create_workspace(
            WorkspaceCreate(
                name="Missing Owner",
                kind="personal",
                base_currency_code="USD",
                owner_user_id=uuid4(),
            ),
            session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Owner user not found"
    assert session.added == []


async def test_create_workspace_returns_404_when_currency_missing() -> None:
    owner_user_id = uuid4()
    session = _FakeAsyncSession(owner_user_id, None)

    with pytest.raises(HTTPException) as exc_info:
        await create_workspace(
            WorkspaceCreate(
                name="Missing Currency",
                kind="personal",
                base_currency_code="ZZZ",
                owner_user_id=owner_user_id,
            ),
            session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Base currency not found"
    assert session.added == []


async def test_create_workspace_rolls_back_integrity_errors() -> None:
    owner_user_id = uuid4()
    session = _FakeAsyncSession(
        owner_user_id,
        "USD",
        commit_error=IntegrityError("insert", {}, Exception("constraint")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workspace(
            WorkspaceCreate(
                name="Personal",
                kind="personal",
                base_currency_code="USD",
                owner_user_id=owner_user_id,
            ),
            session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unable to create workspace"
    assert session.rolled_back is True


async def test_list_workspaces_returns_workspaces_for_member() -> None:
    workspaces = [_workspace(), _workspace()]
    session = _FakeAsyncSession(workspaces)

    result = await list_workspaces(uuid4(), session)  # type: ignore[arg-type]

    assert result == workspaces
    assert len(session.statements) == 1


async def test_get_workspace_returns_404_when_missing() -> None:
    session = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await get_workspace(uuid4(), uuid4(), session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Workspace not found"


async def test_get_workspace_returns_workspace_for_member() -> None:
    workspace = _workspace()
    session = _FakeAsyncSession(workspace)

    result = await get_workspace(workspace.id, uuid4(), session)  # type: ignore[arg-type]

    assert result is workspace
    assert len(session.statements) == 1


async def test_list_workspace_members_returns_404_when_workspace_missing() -> None:
    session = _FakeAsyncSession(None)

    with pytest.raises(HTTPException) as exc_info:
        await list_workspace_members(uuid4(), uuid4(), session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Workspace not found"


async def test_list_workspace_members_returns_members_for_member() -> None:
    workspace_id = uuid4()
    members = [
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=uuid4(),
            role="owner",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    ]
    session = _FakeAsyncSession(workspace_id, members)

    result = await list_workspace_members(  # type: ignore[arg-type]
        workspace_id,
        uuid4(),
        session,
    )

    assert result == members
    assert len(session.statements) == 2


async def test_add_workspace_member_requires_owner_or_admin() -> None:
    workspace_id = uuid4()
    current_user_id = uuid4()
    target_user_id = uuid4()
    session = _FakeAsyncSession(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=current_user_id,
            role="member",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await add_workspace_member(  # type: ignore[arg-type]
            workspace_id,
            WorkspaceMemberCreate(user_id=target_user_id, role="viewer"),
            current_user_id,
            session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Workspace admin permission required"
    assert session.added == []


async def test_add_workspace_member_creates_membership_for_existing_user() -> None:
    workspace_id = uuid4()
    current_user_id = uuid4()
    target_user_id = uuid4()
    session = _FakeAsyncSession(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=current_user_id,
            role="admin",
        ),
        target_user_id,
    )

    membership = await add_workspace_member(  # type: ignore[arg-type]
        workspace_id,
        WorkspaceMemberCreate(user_id=target_user_id, role="member"),
        current_user_id,
        session,
    )

    assert isinstance(membership, WorkspaceMember)
    assert membership.workspace_id == workspace_id
    assert membership.user_id == target_user_id
    assert membership.role == "member"
    assert session.added == [membership]
    assert session.committed is True
    assert session.refreshed is membership


async def test_add_workspace_member_returns_404_when_target_user_missing() -> None:
    workspace_id = uuid4()
    current_user_id = uuid4()
    target_user_id = uuid4()
    session = _FakeAsyncSession(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=current_user_id,
            role="owner",
        ),
        None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await add_workspace_member(  # type: ignore[arg-type]
            workspace_id,
            WorkspaceMemberCreate(user_id=target_user_id, role="member"),
            current_user_id,
            session,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"
    assert session.added == []


async def test_add_workspace_member_rolls_back_duplicate_membership() -> None:
    workspace_id = uuid4()
    current_user_id = uuid4()
    target_user_id = uuid4()
    session = _FakeAsyncSession(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=current_user_id,
            role="owner",
        ),
        target_user_id,
        commit_error=IntegrityError("insert", {}, Exception("duplicate")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await add_workspace_member(  # type: ignore[arg-type]
            workspace_id,
            WorkspaceMemberCreate(user_id=target_user_id, role="viewer"),
            current_user_id,
            session,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unable to add workspace member"
    assert session.rolled_back is True
