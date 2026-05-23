from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_workspace_member, require_workspace_writer
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
from app.services.audit import (
    audit_snapshot,
    ensure_audit_entity_id,
    record_audit_event,
)
from app.services.category_rules import find_matching_rule, validate_rule_definition

router = APIRouter(tags=["category-rules"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
_RULE_AUDIT_FIELDS = [
    "category_id",
    "name",
    "operator",
    "match_field",
    "pattern",
    "amount_min",
    "amount_max",
    "priority",
    "is_active",
]
_TRANSACTION_CATEGORY_AUDIT_FIELDS = ["category_id", "categorized_by"]


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
    dependencies=[Depends(require_workspace_member)],
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
    dependencies=[Depends(require_workspace_writer)],
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
    record_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=None,
        entity_type="category_rule",
        entity_id=ensure_audit_entity_id(rule),
        action="create",
        new_data=audit_snapshot(rule, _RULE_AUDIT_FIELDS),
    )
    await session.commit()
    await session.refresh(rule)
    return rule


@router.patch(
    "/workspaces/{workspace_id}/category-rules/{rule_id}",
    response_model=CategoryRuleRead,
    dependencies=[Depends(require_workspace_writer)],
)
async def update_category_rule(
    workspace_id: UUID,
    rule_id: UUID,
    payload: CategoryRuleUpdate,
    session: SessionDep,
) -> CategoryRule:
    # Scope the lookup to the workspace so a rule cannot be updated across
    # tenants; a rule in another workspace reads as "not found".
    result = await session.execute(
        select(CategoryRule).where(
            CategoryRule.id == rule_id,
            CategoryRule.workspace_id == workspace_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category rule not found"
        )

    old_data = audit_snapshot(rule, _RULE_AUDIT_FIELDS)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    try:
        validate_rule_definition(
            rule.operator, rule.pattern, rule.amount_min, rule.amount_max
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=None,
        entity_type="category_rule",
        entity_id=rule.id,
        action="update",
        old_data=old_data,
        new_data=audit_snapshot(rule, _RULE_AUDIT_FIELDS),
    )
    await session.commit()
    await session.refresh(rule)
    return rule


@router.post(
    "/workspaces/{workspace_id}/category-rules/apply",
    response_model=CategoryRuleApplyResult,
    dependencies=[Depends(require_workspace_writer)],
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
            # Only auto-categorize live ledger rows; never touch transactions
            # marked duplicate, ignored, deleted, or still pending.
            Transaction.status == "posted",
        )
    )
    transactions = list(tx_result.scalars().all())

    # Match rows are unique on (category_rule_id, transaction_id). A
    # transaction that was categorized and later uncategorized can be matched
    # by the same rule again; re-inserting its audit row would trip the
    # unique constraint, so skip matches that already exist.
    existing_result = await session.execute(
        select(
            CategoryRuleMatch.category_rule_id,
            CategoryRuleMatch.transaction_id,
        ).where(CategoryRuleMatch.workspace_id == workspace_id)
    )
    existing_matches = {tuple(row) for row in existing_result.all()}

    categorized_ids: list[UUID] = []
    for transaction in transactions:
        rule = find_matching_rule(rules, transaction)
        if rule is None:
            continue
        old_data = audit_snapshot(transaction, _TRANSACTION_CATEGORY_AUDIT_FIELDS)
        transaction.category_id = rule.category_id
        transaction.categorized_by = "rule"
        if (rule.id, transaction.id) not in existing_matches:
            session.add(
                CategoryRuleMatch(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    category_rule_id=rule.id,
                    transaction_id=transaction.id,
                    matched_value=getattr(transaction, rule.match_field, None),
                )
            )
        record_audit_event(
            session,
            workspace_id=workspace_id,
            user_id=None,
            entity_type="transaction",
            entity_id=transaction.id,
            action="categorize",
            old_data=old_data,
            new_data=audit_snapshot(transaction, _TRANSACTION_CATEGORY_AUDIT_FIELDS),
        )
        categorized_ids.append(transaction.id)

    await session.commit()
    return CategoryRuleApplyResult(
        evaluated_count=len(transactions),
        categorized_count=len(categorized_ids),
        transaction_ids=categorized_ids,
    )
