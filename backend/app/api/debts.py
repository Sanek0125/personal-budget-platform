from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_workspace_member, require_workspace_writer
from app.db.session import get_db_session
from app.models.debt import Contact, Debt, DebtPayment
from app.models.transaction import Transaction
from app.models.workspace import Workspace
from app.schemas.debt import (
    DebtCreate,
    DebtPaymentCreate,
    DebtPaymentRead,
    DebtRead,
    DebtSummaryRead,
)
from app.services.debts import calculate_debt_summary, paid_amount

router = APIRouter(tags=["debts"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _now() -> datetime:
    return datetime.now(UTC)


async def _ensure_workspace_exists(session: AsyncSession, workspace_id: UUID) -> None:
    result = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


async def _get_contact_in_workspace(
    session: AsyncSession, workspace_id: UUID, contact_id: UUID
) -> Contact:
    result = await session.execute(
        select(Contact).where(
            Contact.id == contact_id, Contact.workspace_id == workspace_id
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found in this workspace",
        )
    return contact


async def _get_debt_in_workspace(
    session: AsyncSession, workspace_id: UUID, debt_id: UUID
) -> Debt:
    result = await session.execute(
        select(Debt)
        .options(selectinload(Debt.payments))
        .where(Debt.id == debt_id, Debt.workspace_id == workspace_id)
    )
    debt = result.scalar_one_or_none()
    if debt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found"
        )
    return debt


async def _get_source_transaction(
    session: AsyncSession, workspace_id: UUID, transaction_id: UUID, currency_code: str
) -> Transaction:
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None or transaction.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source transaction not found in this workspace",
        )
    if transaction.currency_code != currency_code:
        raise HTTPException(
            status_code=422,
            detail="Source transaction currency must match debt currency",
        )
    return transaction


async def _get_payment_transaction(
    session: AsyncSession, workspace_id: UUID, transaction_id: UUID, currency_code: str
) -> Transaction:
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None or transaction.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment transaction not found in this workspace",
        )
    if transaction.currency_code != currency_code:
        raise HTTPException(
            status_code=422,
            detail="Payment transaction currency must match debt currency",
        )
    return transaction


@router.get(
    "/workspaces/{workspace_id}/debts",
    response_model=list[DebtRead],
    dependencies=[Depends(require_workspace_member)],
)
async def list_debts(
    workspace_id: UUID,
    session: SessionDep,
    status_filter: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Debt]:
    query = (
        select(Debt)
        .options(selectinload(Debt.payments))
        .where(Debt.workspace_id == workspace_id)
        .order_by(Debt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None:
        query = query.where(Debt.status == status_filter)
    result = await session.execute(query)
    return list(result.scalars().unique().all())


@router.post(
    "/workspaces/{workspace_id}/debts",
    response_model=DebtRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_debt(
    workspace_id: UUID,
    payload: DebtCreate,
    session: SessionDep,
) -> Debt:
    await _ensure_workspace_exists(session, workspace_id)
    if payload.source_transaction_id is not None:
        await _get_source_transaction(
            session, workspace_id, payload.source_transaction_id, payload.currency_code
        )

    contact: Contact | None = None
    if payload.contact_id is not None:
        contact = await _get_contact_in_workspace(
            session, workspace_id, payload.contact_id
        )
    else:
        contact = Contact(
            id=uuid4(),
            workspace_id=workspace_id,
            display_name=payload.contact_name or "",
        )

    debt = Debt(
        id=uuid4(),
        workspace_id=workspace_id,
        contact_id=contact.id,
        direction=payload.direction,
        status="open",
        principal_amount=payload.principal_amount,
        currency_code=payload.currency_code,
        description=payload.description,
        due_date=payload.due_date,
        source_transaction_id=payload.source_transaction_id,
        opened_at=_now(),
    )
    try:
        if payload.contact_id is None:
            session.add(contact)
        session.add(debt)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debt conflicts with existing data",
        ) from exc
    await session.refresh(debt)
    return debt


@router.post(
    "/workspaces/{workspace_id}/debts/{debt_id}/payments",
    response_model=DebtPaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_debt_payment(
    workspace_id: UUID,
    debt_id: UUID,
    payload: DebtPaymentCreate,
    session: SessionDep,
) -> DebtPayment:
    debt = await _get_debt_in_workspace(session, workspace_id, debt_id)
    if debt.status == "cancelled":
        raise HTTPException(status_code=422, detail="Cancelled debt cannot be paid")
    if payload.currency_code != debt.currency_code:
        raise HTTPException(
            status_code=422,
            detail="Debt payment currency must match debt currency",
        )
    current_paid = paid_amount(debt)
    if current_paid + payload.amount > debt.principal_amount:
        raise HTTPException(
            status_code=422,
            detail="Debt payment would exceed principal amount",
        )
    if payload.transaction_id is not None:
        await _get_payment_transaction(
            session, workspace_id, payload.transaction_id, payload.currency_code
        )

    payment = DebtPayment(
        id=uuid4(),
        debt_id=debt.id,
        amount=payload.amount,
        currency_code=payload.currency_code,
        paid_at=payload.paid_at or _now(),
        notes=payload.notes,
        transaction_id=payload.transaction_id,
    )
    next_paid = current_paid + payment.amount
    if next_paid == debt.principal_amount:
        debt.status = "paid"
        debt.closed_at = _now()
    elif next_paid > Decimal("0"):
        debt.status = "partially_paid"
        debt.closed_at = None

    try:
        session.add(payment)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debt payment conflicts with existing data",
        ) from exc
    await session.refresh(payment)
    return payment


@router.get(
    "/workspaces/{workspace_id}/debts/summary",
    response_model=DebtSummaryRead,
    dependencies=[Depends(require_workspace_member)],
)
async def get_debt_summary(workspace_id: UUID, session: SessionDep) -> DebtSummaryRead:
    result = await session.execute(
        select(Debt)
        .options(selectinload(Debt.payments))
        .where(Debt.workspace_id == workspace_id)
    )
    summary = calculate_debt_summary(list(result.scalars().unique().all()))
    summary.workspace_id = workspace_id
    return summary
