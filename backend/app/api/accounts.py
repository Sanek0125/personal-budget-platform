from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.account import Account
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.account import AccountCreate, AccountRead

router = APIRouter(prefix="/workspaces/{workspace_id}/accounts", tags=["accounts"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    workspace_id: UUID,
    session: SessionDep,
) -> list[Account]:
    result = await session.execute(
        select(Account)
        .where(Account.workspace_id == workspace_id)
        .order_by(Account.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    workspace_id: UUID,
    payload: AccountCreate,
    session: SessionDep,
) -> Account:
    workspace = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if workspace.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    if payload.owner_user_id is not None:
        owner_membership = await session.execute(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == payload.owner_user_id,
            )
        )
        if owner_membership.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=422,
                detail="Account owner must be a workspace member",
            )

    account = Account(workspace_id=workspace_id, **payload.model_dump())
    session.add(account)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=422,
            detail="Unknown currency or owner for account",
        ) from exc
    await session.refresh(account)
    return account
