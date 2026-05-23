from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_workspace_member, require_workspace_writer
from app.db.session import get_db_session
from app.models.budget import Budget, BudgetLimit
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.workspace import Workspace
from app.schemas.budget import (
    BudgetCreate,
    BudgetLimitCreate,
    BudgetLimitRead,
    BudgetProgressRead,
    BudgetRead,
)
from app.services.audit import (
    audit_snapshot,
    ensure_audit_entity_id,
    record_audit_event,
)
from app.services.budgets import calculate_budget_progress

router = APIRouter(tags=["budgets"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
_BUDGET_AUDIT_FIELDS = [
    "name",
    "period_type",
    "period_start",
    "period_end",
    "currency_code",
    "is_active",
]
_BUDGET_LIMIT_AUDIT_FIELDS = [
    "budget_id",
    "category_id",
    "amount",
    "currency_code",
    "rollover",
]


async def _ensure_workspace_exists(session: AsyncSession, workspace_id: UUID) -> None:
    result = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


async def _get_budget(session: AsyncSession, budget_id: UUID) -> Budget:
    result = await session.execute(
        select(Budget)
        .options(selectinload(Budget.limits))
        .where(Budget.id == budget_id)
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found"
        )
    return budget


async def _get_category_in_workspace(
    session: AsyncSession, workspace_id: UUID, category_id: UUID
) -> Category:
    result = await session.execute(
        select(Category).where(
            Category.id == category_id,
            Category.workspace_id == workspace_id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found in this workspace",
        )
    return category


@router.get(
    "/workspaces/{workspace_id}/budgets",
    response_model=list[BudgetRead],
    dependencies=[Depends(require_workspace_member)],
)
async def list_budgets(
    workspace_id: UUID,
    session: SessionDep,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Budget]:
    query = (
        select(Budget)
        .where(Budget.workspace_id == workspace_id)
        .order_by(Budget.period_start.desc(), Budget.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if not include_inactive:
        query = query.where(Budget.is_active.is_(True))
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post(
    "/workspaces/{workspace_id}/budgets",
    response_model=BudgetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_budget(
    workspace_id: UUID,
    payload: BudgetCreate,
    session: SessionDep,
) -> Budget:
    await _ensure_workspace_exists(session, workspace_id)
    budget = Budget(
        id=uuid4(),
        workspace_id=workspace_id,
        name=payload.name,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        currency_code=payload.currency_code,
        is_active=payload.is_active,
    )
    try:
        session.add(budget)
        record_audit_event(
            session,
            workspace_id=workspace_id,
            user_id=None,
            entity_type="budget",
            entity_id=ensure_audit_entity_id(budget),
            action="create",
            new_data=audit_snapshot(budget, _BUDGET_AUDIT_FIELDS),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Budget conflicts with existing data",
        ) from exc
    await session.refresh(budget)
    return budget


@router.post(
    "/budgets/{budget_id}/limits",
    response_model=BudgetLimitRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_budget_limit(
    budget_id: UUID,
    payload: BudgetLimitCreate,
    session: SessionDep,
) -> BudgetLimit:
    budget = await _get_budget(session, budget_id)
    await _get_category_in_workspace(session, budget.workspace_id, payload.category_id)
    if payload.currency_code != budget.currency_code:
        raise HTTPException(
            status_code=422,
            detail="Budget limit currency must match budget currency",
        )
    limit = BudgetLimit(
        id=uuid4(),
        budget_id=budget.id,
        category_id=payload.category_id,
        amount=payload.amount,
        currency_code=payload.currency_code,
        rollover=payload.rollover,
    )
    try:
        session.add(limit)
        record_audit_event(
            session,
            workspace_id=budget.workspace_id,
            user_id=None,
            entity_type="budget_limit",
            entity_id=ensure_audit_entity_id(limit),
            action="create",
            new_data=audit_snapshot(limit, _BUDGET_LIMIT_AUDIT_FIELDS),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Budget limit conflicts with existing data",
        ) from exc
    await session.refresh(limit)
    return limit


@router.get("/budgets/{budget_id}/progress", response_model=BudgetProgressRead)
async def get_budget_progress(
    budget_id: UUID,
    session: SessionDep,
) -> BudgetProgressRead:
    budget = await _get_budget(session, budget_id)
    period_start = datetime.combine(budget.period_start, time.min, tzinfo=UTC)
    period_end_exclusive = datetime.combine(
        budget.period_end + timedelta(days=1), time.min, tzinfo=UTC
    )
    result = await session.execute(
        select(Transaction)
        .options(selectinload(Transaction.splits))
        .where(
            Transaction.workspace_id == budget.workspace_id,
            Transaction.deleted_at.is_(None),
            Transaction.status == "posted",
            Transaction.type == "expense",
            Transaction.occurred_at >= period_start,
            Transaction.occurred_at < period_end_exclusive,
        )
    )
    transactions = list(result.scalars().unique().all())
    return calculate_budget_progress(budget, list(budget.limits), transactions)
