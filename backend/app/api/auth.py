from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.workspace import WorkspaceMember

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserHeader = Annotated[UUID | None, Header(alias="X-User-Id")]
WRITE_ROLES = frozenset({"owner", "admin", "member"})


def get_current_user_id(x_user_id: CurrentUserHeader = None) -> UUID:
    """Temporary development auth: identify the requester by X-User-Id."""
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    return x_user_id


CurrentUserDep = Annotated[UUID, Depends(get_current_user_id)]


async def require_workspace_member(
    workspace_id: UUID,
    current_user_id: CurrentUserDep,
    session: SessionDep,
) -> WorkspaceMember:
    result = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return membership


WorkspaceMemberDep = Annotated[WorkspaceMember, Depends(require_workspace_member)]


async def require_workspace_writer(
    workspace_id: UUID,
    current_user_id: CurrentUserDep,
    session: SessionDep,
) -> WorkspaceMember:
    membership = await require_workspace_member(workspace_id, current_user_id, session)
    if membership.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace write permission required",
        )
    return membership


WorkspaceWriterDep = Annotated[WorkspaceMember, Depends(require_workspace_writer)]
