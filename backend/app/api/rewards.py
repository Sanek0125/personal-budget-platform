from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_workspace_member, require_workspace_writer
from app.db.session import get_db_session
from app.models.category import Category
from app.models.reward import CashbackRule, RewardEvent, RewardProgram
from app.models.transaction import Transaction
from app.models.workspace import Workspace
from app.schemas.reward import (
    CashbackRuleCreate,
    CashbackRuleRead,
    ExpectedRewardRead,
    ExpectedRewardRequest,
    RewardEventCreate,
    RewardEventRead,
    RewardProgramCreate,
    RewardProgramRead,
)
from app.services.rewards import calculate_reward_for_transaction

router = APIRouter(tags=["rewards"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def _ensure_workspace_exists(session: AsyncSession, workspace_id: UUID) -> None:
    result = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


async def _get_program(
    session: AsyncSession, workspace_id: UUID, program_id: UUID
) -> RewardProgram:
    result = await session.execute(
        select(RewardProgram).where(
            RewardProgram.id == program_id,
            RewardProgram.workspace_id == workspace_id,
        )
    )
    program = result.scalar_one_or_none()
    if program is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reward program not found in this workspace",
        )
    return program


async def _get_transaction(
    session: AsyncSession, workspace_id: UUID, transaction_id: UUID, detail: str
) -> Transaction:
    result = await session.execute(
        select(Transaction)
        .options(selectinload(Transaction.splits))
        .where(
            Transaction.id == transaction_id,
            Transaction.workspace_id == workspace_id,
            Transaction.deleted_at.is_(None),
        )
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return transaction


async def _ensure_category_in_workspace(
    session: AsyncSession, workspace_id: UUID, category_id: UUID
) -> None:
    result = await session.execute(
        select(Category.id).where(
            Category.id == category_id,
            Category.workspace_id == workspace_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found in this workspace",
        )


async def _get_cashback_rule_for_program(
    session: AsyncSession,
    workspace_id: UUID,
    program_id: UUID,
    rule_id: UUID,
) -> CashbackRule:
    result = await session.execute(
        select(CashbackRule).where(
            CashbackRule.id == rule_id,
            CashbackRule.workspace_id == workspace_id,
            CashbackRule.program_id == program_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cashback rule not found for this reward program",
        )
    return rule


@router.get(
    "/workspaces/{workspace_id}/rewards/programs",
    response_model=list[RewardProgramRead],
    dependencies=[Depends(require_workspace_member)],
)
async def list_reward_programs(
    workspace_id: UUID,
    session: SessionDep,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RewardProgram]:
    query = (
        select(RewardProgram)
        .where(RewardProgram.workspace_id == workspace_id)
        .order_by(RewardProgram.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if is_active is not None:
        query = query.where(RewardProgram.is_active.is_(is_active))
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post(
    "/workspaces/{workspace_id}/rewards/programs",
    response_model=RewardProgramRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_reward_program(
    workspace_id: UUID,
    payload: RewardProgramCreate,
    session: SessionDep,
) -> RewardProgram:
    await _ensure_workspace_exists(session, workspace_id)
    program = RewardProgram(
        id=uuid4(),
        workspace_id=workspace_id,
        name=payload.name,
        program_type=payload.program_type,
        currency_code=payload.currency_code,
        issuer_name=payload.issuer_name,
        is_active=payload.is_active,
        notes=payload.notes,
    )
    try:
        session.add(program)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Reward program conflicts with existing data"
        ) from exc
    await session.refresh(program)
    return program


@router.post(
    "/workspaces/{workspace_id}/rewards/cashback-rules",
    response_model=CashbackRuleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_cashback_rule(
    workspace_id: UUID,
    payload: CashbackRuleCreate,
    session: SessionDep,
) -> CashbackRule:
    await _get_program(session, workspace_id, payload.program_id)
    if payload.category_id is not None:
        await _ensure_category_in_workspace(session, workspace_id, payload.category_id)
    rule = CashbackRule(
        id=uuid4(),
        workspace_id=workspace_id,
        program_id=payload.program_id,
        name=payload.name,
        rate=payload.rate,
        spend_currency_code=payload.spend_currency_code,
        category_id=payload.category_id,
        merchant_pattern=payload.merchant_pattern,
        min_spend_amount=payload.min_spend_amount,
        max_reward_amount=payload.max_reward_amount,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    try:
        session.add(rule)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Cashback rule conflicts with existing data"
        ) from exc
    await session.refresh(rule)
    return rule


@router.get(
    "/workspaces/{workspace_id}/rewards/events",
    response_model=list[RewardEventRead],
    dependencies=[Depends(require_workspace_member)],
)
async def list_reward_events(
    workspace_id: UUID,
    session: SessionDep,
    program_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RewardEvent]:
    query = (
        select(RewardEvent)
        .where(RewardEvent.workspace_id == workspace_id)
        .order_by(RewardEvent.occurred_at.desc(), RewardEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if program_id is not None:
        query = query.where(RewardEvent.program_id == program_id)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post(
    "/workspaces/{workspace_id}/rewards/events",
    response_model=RewardEventRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_reward_event(
    workspace_id: UUID,
    payload: RewardEventCreate,
    session: SessionDep,
) -> RewardEvent:
    program = await _get_program(session, workspace_id, payload.program_id)
    if payload.reward_kind != program.program_type:
        raise HTTPException(
            status_code=422, detail="Reward event kind must match program type"
        )
    if payload.currency_code != program.currency_code:
        raise HTTPException(
            status_code=422, detail="Reward event currency must match program currency"
        )
    if payload.cashback_rule_id is not None:
        await _get_cashback_rule_for_program(
            session,
            workspace_id,
            payload.program_id,
            payload.cashback_rule_id,
        )
    if payload.source_transaction_id is not None:
        await _get_transaction(
            session,
            workspace_id,
            payload.source_transaction_id,
            "Source transaction not found in this workspace",
        )
    if payload.reward_transaction_id is not None:
        await _get_transaction(
            session,
            workspace_id,
            payload.reward_transaction_id,
            "Reward transaction not found in this workspace",
        )
    event = RewardEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        program_id=payload.program_id,
        cashback_rule_id=payload.cashback_rule_id,
        source_transaction_id=payload.source_transaction_id,
        reward_transaction_id=payload.reward_transaction_id,
        event_type=payload.event_type,
        status=payload.status,
        reward_kind=payload.reward_kind,
        amount=payload.amount,
        currency_code=payload.currency_code,
        occurred_at=payload.occurred_at,
        description=payload.description or f"{program.name} reward",
        notes=payload.notes,
    )
    try:
        session.add(event)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Reward event conflicts with existing data"
        ) from exc
    await session.refresh(event)
    return event


@router.post(
    "/workspaces/{workspace_id}/rewards/expected",
    response_model=ExpectedRewardRead,
    dependencies=[Depends(require_workspace_member)],
)
async def calculate_expected_reward(
    workspace_id: UUID,
    payload: ExpectedRewardRequest,
    session: SessionDep,
) -> ExpectedRewardRead:
    program = await _get_program(session, workspace_id, payload.program_id)
    transaction = await _get_transaction(
        session,
        workspace_id,
        payload.source_transaction_id,
        "Source transaction not found in this workspace",
    )
    result = await session.execute(
        select(CashbackRule)
        .where(
            CashbackRule.workspace_id == workspace_id,
            CashbackRule.program_id == program.id,
            CashbackRule.is_active.is_(True),
        )
        .order_by(CashbackRule.priority.asc(), CashbackRule.created_at.asc())
    )
    rules = list(result.scalars().all())
    calculation = calculate_reward_for_transaction(program, transaction, rules)
    if calculation is None:
        raise HTTPException(
            status_code=404, detail="No matching reward rule for transaction"
        )
    return calculation
