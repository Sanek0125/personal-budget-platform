from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_workspace_member, require_workspace_writer
from app.db.session import get_db_session
from app.models.category import Category
from app.models.workspace import Workspace
from app.schemas.category import CategoryCreate, CategoryRead
from app.services.audit import (
    audit_snapshot,
    ensure_audit_entity_id,
    record_audit_event,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/categories", tags=["categories"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
_CATEGORY_AUDIT_FIELDS = [
    "parent_id",
    "name",
    "type",
    "color",
    "icon",
    "is_system",
    "sort_order",
]


@router.get(
    "",
    response_model=list[CategoryRead],
    dependencies=[Depends(require_workspace_member)],
)
async def list_categories(
    workspace_id: UUID,
    session: SessionDep,
) -> list[Category]:
    result = await session.execute(
        select(Category)
        .where(Category.workspace_id == workspace_id)
        .order_by(Category.sort_order, Category.name)
    )
    return list(result.scalars().all())


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_category(
    workspace_id: UUID,
    payload: CategoryCreate,
    session: SessionDep,
) -> Category:
    workspace = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if workspace.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    if payload.parent_id is not None:
        parent = await session.execute(
            select(Category).where(
                Category.id == payload.parent_id,
                Category.workspace_id == workspace_id,
            )
        )
        if parent.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found in this workspace",
            )

    duplicate_query = select(Category).where(
        Category.workspace_id == workspace_id,
        Category.name == payload.name,
    )
    if payload.parent_id is None:
        duplicate_query = duplicate_query.where(Category.parent_id.is_(None))
    else:
        duplicate_query = duplicate_query.where(Category.parent_id == payload.parent_id)

    duplicate = await session.execute(duplicate_query)
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category name already exists under the same parent",
        )

    category = Category(workspace_id=workspace_id, **payload.model_dump())
    session.add(category)
    record_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=None,
        entity_type="category",
        entity_id=ensure_audit_entity_id(category),
        action="create",
        new_data=audit_snapshot(category, _CATEGORY_AUDIT_FIELDS),
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category name already exists under the same parent",
        ) from exc
    await session.refresh(category)
    return category
