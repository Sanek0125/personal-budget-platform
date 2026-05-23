from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUserDep, get_current_user_id
from app.db.session import get_db_session
from app.models.currency import Currency
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceMemberRead, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(
    user_id: CurrentUserDep,
    session: SessionDep,
) -> list[Workspace]:
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.created_at, Workspace.id)
    )
    return list(result.scalars().all())


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: UUID,
    user_id: CurrentUserDep,
    session: SessionDep,
) -> Workspace:
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user_id)],
)
async def create_workspace(
    payload: WorkspaceCreate,
    session: SessionDep,
) -> Workspace:
    owner = await session.execute(
        select(User.id).where(User.id == payload.owner_user_id)
    )
    if owner.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner user not found",
        )

    currency = await session.execute(
        select(Currency.code).where(Currency.code == payload.base_currency_code)
    )
    if currency.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base currency not found",
        )

    workspace = Workspace(**payload.model_dump())
    membership = WorkspaceMember(
        workspace=workspace,
        user_id=payload.owner_user_id,
        role="owner",
    )
    session.add(workspace)
    session.add(membership)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422,
            detail="Unable to create workspace",
        ) from exc
    await session.refresh(workspace)
    return workspace


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
async def list_workspace_members(
    workspace_id: UUID,
    user_id: CurrentUserDep,
    session: SessionDep,
) -> list[WorkspaceMember]:
    workspace = await session.execute(
        select(Workspace.id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if workspace.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    result = await session.execute(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at, WorkspaceMember.id)
    )
    return list(result.scalars().all())
