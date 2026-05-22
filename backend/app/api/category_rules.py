from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.category import Category
from app.models.category_rule import CategoryRule, CategoryRuleMatch
from app.models.transaction import Transaction
from app.models.workspace import Workspace
from app.schemas.category_rule import (
    CategoryRuleApplyResult,
    CategoryRuleCreate,
    CategoryRuleRead,
    CategoryRuleUpdate,
)
from app.services.category_rules import find_matching_rule, validate_rule_definition

router = APIRouter(tags=["category-rules"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def _ensure_workspace_exists(
    session: AsyncSession, workspace_id: UUID
) -> None:
    result = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


@router.get(
    "/workspaces/{workspace_id}/category-rules",
    response_model=list[CategoryRuleRead],
)
async def list_category_rules(
    workspace_id: UUID,
    session: SessionDep,
) -> list[CategoryRule]:
    result = await session.execute(
        select(CategoryRule)
        .where(CategoryRule.workspace_id == workspace_id)
        .order_by(CategoryRule.priority, CategoryRule.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/workspaces/{workspace_id}/category-rules",
    response_model=CategoryRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category_rule(
    workspace_id: UUID,
    payload: CategoryRuleCreate,
    session: SessionDep,
) -> CategoryRule:
    await _ensure_workspace_exists(session, workspace_id)
    category_result = await session.execute(
        select(Category.id).where(
            Category.id == payload.category_id,
            Category.workspace_id == workspace_id,
        )
    )
    if category_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found in this workspace",
        )

    rule = CategoryRule(
        id=uuid4(),
        workspace_id=workspace_id,
        category_id=payload.category_id,
        name=payload.name,
        operator=payload.operator,
        match_field=payload.match_field,
        pattern=payload.pattern,
        amount_min=payload.amount_min,
        amount_max=payload.amount_max,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.patch(
    "/category-rules/{rule_id}",
    response_model=CategoryRuleRead,
)
async def update_category_rule(
    rule_id: UUID,
    payload: CategoryRuleUpdate,
    session: SessionDep,
) -> CategoryRule:
    result = await session.execute(
        select(CategoryRule).where(CategoryRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category rule not found"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    try:
        validate_rule_definition(
            rule.operator, rule.pattern, rule.amount_min, rule.amount_max
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(rule)
    return rule


@router.post(
    "/workspaces/{workspace_id}/category-rules/apply",
    response_model=CategoryRuleApplyResult,
)
async def apply_category_rules(
    workspace_id: UUID,
    session: SessionDep,
) -> CategoryRuleApplyResult:
    await _ensure_workspace_exists(session, workspace_id)
    rules_result = await session.execute(
        select(CategoryRule)
        .where(
            CategoryRule.workspace_id == workspace_id,
            CategoryRule.is_active.is_(True),
        )
        .order_by(CategoryRule.priority)
    )
    rules = list(rules_result.scalars().all())

    tx_result = await session.execute(
        select(Transaction).where(
            Transaction.workspace_id == workspace_id,
            Transaction.category_id.is_(None),
            Transaction.deleted_at.is_(None),
        )
    )
    transactions = list(tx_result.scalars().all())

    categorized_ids: list[UUID] = []
    for transaction in transactions:
        rule = find_matching_rule(rules, transaction)
        if rule is None:
            continue
        transaction.category_id = rule.category_id
        transaction.categorized_by = "rule"
        session.add(
            CategoryRuleMatch(
                id=uuid4(),
                workspace_id=workspace_id,
                category_rule_id=rule.id,
                transaction_id=transaction.id,
                matched_value=getattr(transaction, rule.match_field, None),
            )
        )
        categorized_ids.append(transaction.id)

    await session.commit()
    return CategoryRuleApplyResult(
        evaluated_count=len(transactions),
        categorized_count=len(categorized_ids),
        transaction_ids=categorized_ids,
    )
