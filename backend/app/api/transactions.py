from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_workspace_member, require_workspace_writer
from app.db.session import get_db_session
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction, TransactionLink, TransactionSplit
from app.models.workspace import Workspace
from app.schemas.transaction import (
    TransactionCreate,
    TransactionRead,
    TransactionSplitCreate,
    TransactionType,
    TransactionUpdate,
    TransferCreate,
    TransferRead,
)
from app.services.audit import (
    audit_snapshot,
    ensure_audit_entity_id,
    record_audit_event,
)
from app.services.transaction_fingerprints import build_transaction_fingerprint

router = APIRouter(
    prefix="/workspaces/{workspace_id}/transactions", tags=["transactions"]
)
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _now() -> datetime:
    return datetime.now(UTC)


# Partial unique index guarding against duplicate active transactions; defined
# in app/models/transaction.py.
_FINGERPRINT_INDEX = "uq_transactions_active_fingerprint"
_TRANSACTION_AUDIT_FIELDS = [
    "account_id",
    "type",
    "status",
    "occurred_at",
    "booked_at",
    "amount",
    "currency_code",
    "base_amount",
    "base_currency_code",
    "description",
    "merchant_name",
    "category_id",
    "categorized_by",
    "notes",
    "source",
    "external_id",
    "fingerprint",
    "deleted_at",
]


def _integrity_conflict(exc: IntegrityError) -> HTTPException:
    """Map an IntegrityError to a 409, naming duplicate-fingerprint clashes.

    Hitting the partial unique index ``uq_transactions_active_fingerprint``
    means the transaction duplicates an existing active one for the account;
    surface that explicitly so callers can tell it apart from other conflicts.
    Any other integrity violation gets a generic 409.
    """
    if _FINGERPRINT_INDEX in str(exc.orig):
        detail = (
            "A transaction with the same fingerprint already exists "
            "for this account"
        )
    else:
        detail = "Transaction conflicts with an existing record"
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _ensure_workspace_exists(session: AsyncSession, workspace_id: UUID) -> None:
    result = await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
        )


async def _get_workspace_account(
    session: AsyncSession, workspace_id: UUID, account_id: UUID
) -> Account:
    result = await session.execute(
        select(Account).where(
            Account.id == account_id, Account.workspace_id == workspace_id
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found in this workspace",
        )
    return account


async def _ensure_category_in_workspace(
    session: AsyncSession,
    workspace_id: UUID,
    category_id: UUID | None,
    detail: str = "Category not found in this workspace",
) -> None:
    if category_id is None:
        return
    result = await session.execute(
        select(Category.id).where(
            Category.id == category_id, Category.workspace_id == workspace_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _validate_transaction_sign(type: str, amount: Decimal) -> None:
    if type == "expense" and amount >= 0:
        raise HTTPException(status_code=422, detail="Expense amount must be negative")
    if type == "income" and amount <= 0:
        raise HTTPException(status_code=422, detail="Income amount must be positive")
    if type in {"transfer", "adjustment"} and amount == 0:
        raise HTTPException(
            status_code=422, detail="Transaction amount must be non-zero"
        )


def _validate_splits(
    parent_amount: Decimal, parent_currency: str, splits: list[TransactionSplitCreate]
) -> None:
    if not splits:
        return
    for split in splits:
        if split.currency_code != parent_currency:
            raise HTTPException(
                status_code=422, detail="Split currency must match transaction currency"
            )
    if sum((split.amount for split in splits), Decimal("0")) != parent_amount:
        raise HTTPException(
            status_code=422, detail="Split amounts must equal transaction amount"
        )


def _set_fingerprint(transaction: Transaction) -> None:
    transaction.fingerprint = build_transaction_fingerprint(
        workspace_id=transaction.workspace_id,
        account_id=transaction.account_id,
        type=transaction.type,
        occurred_at=transaction.occurred_at,
        amount=transaction.amount,
        currency_code=transaction.currency_code,
        description=transaction.description,
        external_id=transaction.external_id,
    )


def _transaction_from_create(
    workspace_id: UUID, payload: TransactionCreate
) -> Transaction:
    transaction = Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=payload.account_id,
        type=payload.type,
        status="posted",
        occurred_at=payload.occurred_at,
        booked_at=payload.booked_at,
        amount=payload.amount,
        currency_code=payload.currency_code,
        original_amount=payload.original_amount,
        original_currency_code=payload.original_currency_code,
        base_amount=payload.base_amount,
        base_currency_code=payload.base_currency_code,
        exchange_rate_id=payload.exchange_rate_id,
        exchange_rate=payload.exchange_rate,
        description=payload.description,
        merchant_name=payload.merchant_name,
        merchant_raw=payload.merchant_raw,
        category_id=payload.category_id,
        notes=payload.notes,
        source=payload.source,
        external_id=payload.external_id,
        fingerprint="",
    )
    _set_fingerprint(transaction)
    return transaction


def _split_rows(
    transaction: Transaction, splits: list[TransactionSplitCreate]
) -> list[TransactionSplit]:
    return [
        TransactionSplit(
            id=uuid4(),
            transaction_id=transaction.id,
            category_id=split.category_id,
            amount=split.amount,
            currency_code=split.currency_code,
            description=split.description,
            sort_order=split.sort_order,
        )
        for split in splits
    ]


@router.get(
    "",
    response_model=list[TransactionRead],
    dependencies=[Depends(require_workspace_member)],
)
async def list_transactions(
    workspace_id: UUID,
    session: SessionDep,
    account_id: UUID | None = None,
    category_id: UUID | None = None,
    type: TransactionType | None = None,
    include_deleted: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Transaction]:
    query = (
        select(Transaction)
        .options(selectinload(Transaction.splits))
        .where(Transaction.workspace_id == workspace_id)
        .order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if category_id is not None:
        query = query.where(
            or_(
                Transaction.category_id == category_id,
                Transaction.splits.any(TransactionSplit.category_id == category_id),
            )
        )
    if type is not None:
        query = query.where(Transaction.type == type)
    if not include_deleted:
        query = query.where(Transaction.deleted_at.is_(None))
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_transaction(
    workspace_id: UUID,
    payload: TransactionCreate,
    session: SessionDep,
) -> Transaction:
    await _ensure_workspace_exists(session, workspace_id)
    account = await _get_workspace_account(session, workspace_id, payload.account_id)
    if payload.currency_code != account.currency_code:
        raise HTTPException(
            status_code=422,
            detail="Transaction currency must match account currency",
        )
    await _ensure_category_in_workspace(session, workspace_id, payload.category_id)
    _validate_splits(payload.amount, payload.currency_code, payload.splits)
    for split in payload.splits:
        await _ensure_category_in_workspace(
            session,
            workspace_id,
            split.category_id,
            "Split category not found in this workspace",
        )

    transaction = _transaction_from_create(workspace_id, payload)
    rows: list[TransactionSplit] = []
    try:
        session.add(transaction)
        await session.flush()
        if payload.splits:
            rows = _split_rows(transaction, payload.splits)
            session.add_all(rows)
            transaction.splits = rows
        record_audit_event(
            session,
            workspace_id=workspace_id,
            user_id=None,
            entity_type="transaction",
            entity_id=ensure_audit_entity_id(transaction),
            action="create",
            new_data=audit_snapshot(transaction, _TRANSACTION_AUDIT_FIELDS),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _integrity_conflict(exc) from exc
    await session.refresh(transaction)
    transaction.splits = rows
    return transaction


async def _get_active_transaction(
    session: AsyncSession, workspace_id: UUID, transaction_id: UUID
) -> Transaction:
    result = await session.execute(
        select(Transaction)
        .options(selectinload(Transaction.splits))
        .where(
            Transaction.id == transaction_id, Transaction.workspace_id == workspace_id
        )
    )
    transaction = result.scalar_one_or_none()
    if (
        transaction is None
        or transaction.status == "deleted"
        or transaction.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )
    return transaction


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    dependencies=[Depends(require_workspace_member)],
)
async def get_transaction(
    workspace_id: UUID,
    transaction_id: UUID,
    session: SessionDep,
) -> Transaction:
    return await _get_active_transaction(session, workspace_id, transaction_id)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionRead,
    dependencies=[Depends(require_workspace_writer)],
)
async def update_transaction(
    workspace_id: UUID,
    transaction_id: UUID,
    payload: TransactionUpdate,
    session: SessionDep,
) -> Transaction:
    transaction = await _get_active_transaction(session, workspace_id, transaction_id)
    old_data = audit_snapshot(transaction, _TRANSACTION_AUDIT_FIELDS)
    if transaction.type == "transfer":
        raise HTTPException(
            status_code=422,
            detail="Transfer transactions cannot be updated directly",
        )
    if payload.category_id is not None:
        await _ensure_category_in_workspace(session, workspace_id, payload.category_id)

    update_data = payload.model_dump(exclude_unset=True, exclude={"splits"})
    if "currency_code" in update_data:
        account = await _get_workspace_account(
            session, workspace_id, transaction.account_id
        )
        if update_data["currency_code"] != account.currency_code:
            raise HTTPException(
                status_code=422,
                detail="Transaction currency must match account currency",
            )

    for field, value in update_data.items():
        setattr(transaction, field, value)
    _validate_transaction_sign(transaction.type, transaction.amount)

    replacement_splits = payload.splits
    rows: list[TransactionSplit] = []
    if replacement_splits is not None:
        _validate_splits(
            transaction.amount, transaction.currency_code, replacement_splits
        )
        old_splits_result = await session.execute(
            select(TransactionSplit).where(
                TransactionSplit.transaction_id == transaction.id
            )
        )
        old_splits = list(old_splits_result.scalars().all())
        for old_split in old_splits:
            await session.delete(old_split)
        for split in replacement_splits:
            await _ensure_category_in_workspace(
                session,
                workspace_id,
                split.category_id,
                "Split category not found in this workspace",
            )
        rows = _split_rows(transaction, replacement_splits)
        session.add_all(rows)
        transaction.splits = rows
    elif transaction.splits:
        _validate_splits(
            transaction.amount, transaction.currency_code, transaction.splits
        )

    _set_fingerprint(transaction)
    record_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=None,
        entity_type="transaction",
        entity_id=transaction.id,
        action="update",
        old_data=old_data,
        new_data=audit_snapshot(transaction, _TRANSACTION_AUDIT_FIELDS),
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _integrity_conflict(exc) from exc
    await session.refresh(transaction)
    if replacement_splits is not None:
        transaction.splits = rows
    return transaction


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_workspace_writer)],
)
async def delete_transaction(
    workspace_id: UUID,
    transaction_id: UUID,
    session: SessionDep,
) -> Response:
    transaction = await _get_active_transaction(session, workspace_id, transaction_id)
    to_delete = [transaction]
    link_result = await session.execute(
        select(TransactionLink).where(
            TransactionLink.workspace_id == workspace_id,
            TransactionLink.relation_type == "transfer_pair",
            or_(
                TransactionLink.transaction_id == transaction_id,
                TransactionLink.linked_transaction_id == transaction_id,
            ),
        )
    )
    link = link_result.scalar_one_or_none()
    if link is not None:
        other_id = (
            link.linked_transaction_id
            if link.transaction_id == transaction_id
            else link.transaction_id
        )
        other_result = await session.execute(
            select(Transaction).where(
                Transaction.id == other_id, Transaction.workspace_id == workspace_id
            )
        )
        other = other_result.scalar_one_or_none()
        if other is not None:
            to_delete.append(other)

    now = _now()
    for row in to_delete:
        old_data = audit_snapshot(row, _TRANSACTION_AUDIT_FIELDS)
        row.status = "deleted"
        row.deleted_at = now
        record_audit_event(
            session,
            workspace_id=workspace_id,
            user_id=None,
            entity_type="transaction",
            entity_id=ensure_audit_entity_id(row),
            action="delete",
            old_data=old_data,
            new_data=audit_snapshot(row, _TRANSACTION_AUDIT_FIELDS),
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/transfers",
    response_model=TransferRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_writer)],
)
async def create_transfer(
    workspace_id: UUID,
    payload: TransferCreate,
    session: SessionDep,
) -> TransferRead:
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=422, detail="Transfer accounts must be different"
        )
    await _ensure_workspace_exists(session, workspace_id)
    from_account = await _get_workspace_account(
        session, workspace_id, payload.from_account_id
    )
    to_account = await _get_workspace_account(
        session, workspace_id, payload.to_account_id
    )

    to_currency = payload.to_currency_code or to_account.currency_code
    if payload.from_currency_code != from_account.currency_code:
        raise HTTPException(
            status_code=422,
            detail="Transfer from_currency_code must match source account currency",
        )
    if to_currency != to_account.currency_code:
        raise HTTPException(
            status_code=422,
            detail="Transfer to_currency_code must match destination account currency",
        )
    if payload.to_amount is None:
        if payload.from_currency_code == to_currency:
            to_amount = payload.from_amount
        elif payload.exchange_rate is None:
            detail = "Cross-currency transfers require to_amount or exchange snapshot"
            raise HTTPException(status_code=422, detail=detail)
        else:
            to_amount = payload.from_amount * payload.exchange_rate
    else:
        to_amount = payload.to_amount

    outflow = Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=from_account.id,
        type="transfer",
        status="posted",
        occurred_at=payload.occurred_at,
        booked_at=payload.booked_at,
        amount=-abs(payload.from_amount),
        currency_code=payload.from_currency_code,
        exchange_rate_id=payload.exchange_rate_id,
        exchange_rate=payload.exchange_rate,
        description=payload.description,
        notes=payload.notes,
        source="manual",
        fingerprint="",
    )
    inflow = Transaction(
        id=uuid4(),
        workspace_id=workspace_id,
        account_id=to_account.id,
        type="transfer",
        status="posted",
        occurred_at=payload.occurred_at,
        booked_at=payload.booked_at,
        amount=abs(to_amount),
        currency_code=to_currency,
        exchange_rate_id=payload.exchange_rate_id,
        exchange_rate=payload.exchange_rate,
        description=payload.description,
        notes=payload.notes,
        source="manual",
        fingerprint="",
    )
    _set_fingerprint(outflow)
    _set_fingerprint(inflow)
    link = TransactionLink(
        id=uuid4(),
        workspace_id=workspace_id,
        transaction_id=outflow.id,
        linked_transaction_id=inflow.id,
        relation_type="transfer_pair",
    )
    session.add_all([outflow, inflow, link])
    for row in (outflow, inflow):
        record_audit_event(
            session,
            workspace_id=workspace_id,
            user_id=None,
            entity_type="transaction",
            entity_id=ensure_audit_entity_id(row),
            action="create",
            new_data=audit_snapshot(row, _TRANSACTION_AUDIT_FIELDS),
        )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _integrity_conflict(exc) from exc
    await session.refresh(outflow)
    await session.refresh(inflow)
    outflow.splits = []
    inflow.splits = []
    return TransferRead(outflow=outflow, inflow=inflow, link_id=link.id)
