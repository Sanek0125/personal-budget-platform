from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models import (
    Account,
    Category,
    File,
    ImportBatch,
    ImportRow,
    Transaction,
    Workspace,
    WorkspaceMember,
)
from app.schemas.imports import (
    CsvImportUpload,
    ImportBatchRead,
    ImportConfirmResult,
    ImportRowRead,
)
from app.services.csv_imports import file_sha256, parse_csv_rows
from app.services.transaction_fingerprints import build_transaction_fingerprint

router = APIRouter(prefix="/workspaces/{workspace_id}/imports", tags=["imports"])
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


async def _ensure_workspace_member(
    session: AsyncSession, workspace_id: UUID, user_id: UUID
) -> None:
    owner_result = await session.execute(
        select(Workspace.owner_user_id).where(Workspace.id == workspace_id)
    )
    owner_user_id = owner_result.scalar_one_or_none()
    if owner_user_id == user_id:
        return
    member_result = await session.execute(
        select(WorkspaceMember.id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if member_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this workspace",
        )


async def _get_import_batch(
    session: AsyncSession, workspace_id: UUID, import_batch_id: UUID
) -> ImportBatch:
    result = await session.execute(
        select(ImportBatch).where(
            ImportBatch.id == import_batch_id,
            ImportBatch.workspace_id == workspace_id,
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found"
        )
    return batch


async def _ensure_category_in_workspace(
    session: AsyncSession, workspace_id: UUID, category_id: UUID | None
) -> None:
    if category_id is None:
        return
    result = await session.execute(
        select(Category.id).where(
            Category.id == category_id, Category.workspace_id == workspace_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found in this workspace",
        )


def _conflict(exc: IntegrityError) -> HTTPException:
    if "uq_import_batches_workspace_file_hash" in str(exc.orig):
        detail = "This file has already been imported for the workspace"
    elif "uq_import_rows_batch_raw_hash" in str(exc.orig):
        detail = "CSV file contains duplicate raw rows"
    else:
        detail = "Import conflicts with an existing record"
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _storage_key(workspace_id: UUID, sha256: str, filename: str) -> str:
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"imports/{workspace_id}/{sha256}/{safe_name}"


@router.post(
    "/upload",
    response_model=ImportBatchRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_csv_import(
    workspace_id: UUID,
    payload: CsvImportUpload,
    session: SessionDep,
) -> ImportBatch:
    await _ensure_workspace_exists(session, workspace_id)
    account = await _get_workspace_account(session, workspace_id, payload.account_id)
    await _ensure_workspace_member(session, workspace_id, payload.user_id)

    parsed_rows = parse_csv_rows(payload.content, payload.column_mapping)
    digest = file_sha256(payload.content)
    uploaded_file = File(
        id=uuid4(),
        workspace_id=workspace_id,
        uploaded_by_user_id=payload.user_id,
        original_filename=payload.original_filename,
        content_type="text/csv",
        size_bytes=len(payload.content.encode("utf-8")),
        storage_key=_storage_key(workspace_id, digest, payload.original_filename),
        sha256=digest,
    )
    batch = ImportBatch(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=payload.user_id,
        account_id=account.id,
        file_id=uploaded_file.id,
        source_type="csv",
        source_name=payload.source_name,
        original_filename=payload.original_filename,
        file_hash=digest,
        file_size=uploaded_file.size_bytes,
        status="parsed",
        total_rows=len(parsed_rows),
        parser_version="csv-v1",
    )
    rows = [
        ImportRow(
            id=uuid4(),
            import_batch_id=batch.id,
            workspace_id=workspace_id,
            row_number=row.row_number,
            raw_data=row.raw_data,
            normalized_data=row.normalized_data,
            raw_hash=row.raw_hash,
            normalized_hash=row.normalized_hash,
            status="pending",
        )
        for row in parsed_rows
    ]
    try:
        session.add_all([uploaded_file, batch, *rows])
        await session.flush()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _conflict(exc) from exc
    await session.refresh(batch)
    return batch


@router.get("/{import_batch_id}", response_model=ImportBatchRead)
async def get_import_batch(
    workspace_id: UUID, import_batch_id: UUID, session: SessionDep
) -> ImportBatch:
    return await _get_import_batch(session, workspace_id, import_batch_id)


@router.get("/{import_batch_id}/rows", response_model=list[ImportRowRead])
async def list_import_rows(
    workspace_id: UUID,
    import_batch_id: UUID,
    session: SessionDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ImportRow]:
    await _get_import_batch(session, workspace_id, import_batch_id)
    query = (
        select(ImportRow)
        .where(
            ImportRow.import_batch_id == import_batch_id,
            ImportRow.workspace_id == workspace_id,
        )
        .order_by(ImportRow.row_number)
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None:
        query = query.where(ImportRow.status == status_filter)
    result = await session.execute(query)
    return list(result.scalars().all())


def _date_or_none(value: object) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _validate_transaction_sign(transaction_type: str, amount: Decimal) -> None:
    if transaction_type == "expense" and amount >= 0:
        raise HTTPException(status_code=422, detail="Expense amount must be negative")
    if transaction_type == "income" and amount <= 0:
        raise HTTPException(status_code=422, detail="Income amount must be positive")
    if transaction_type == "adjustment" and amount == 0:
        raise HTTPException(
            status_code=422, detail="Transaction amount must be non-zero"
        )


def _category_id(value: object) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid category_id value"
        ) from exc


def _transaction_from_import(
    batch: ImportBatch, row: ImportRow, account: Account
) -> Transaction:
    if row.normalized_data is None:
        raise HTTPException(
            status_code=422, detail=f"Import row {row.row_number} is not normalized"
        )
    data = row.normalized_data
    amount = Decimal(str(data["amount"]))
    currency_code = str(data["currency_code"]).upper()
    if currency_code != account.currency_code:
        raise HTTPException(
            status_code=422,
            detail="Imported transaction currency must match account currency",
        )
    transaction_type = str(data["type"])
    _validate_transaction_sign(transaction_type, amount)
    transaction = Transaction(
        id=uuid4(),
        workspace_id=batch.workspace_id,
        account_id=account.id,
        user_id=batch.user_id,
        type=transaction_type,
        status="posted",
        occurred_at=_datetime(data["occurred_at"]),
        booked_at=_date_or_none(data.get("booked_at")),
        amount=amount,
        currency_code=currency_code,
        description=str(data["description"]),
        merchant_name=data.get("merchant_name"),
        merchant_raw=data.get("merchant_raw"),
        category_id=_category_id(data.get("category_id")),
        source="csv_import",
        import_batch_id=batch.id,
        import_row_id=row.id,
        external_id=data.get("external_id"),
        fingerprint="",
    )
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
    return transaction


async def _find_existing_transaction(
    session: AsyncSession, transaction: Transaction
) -> Transaction | None:
    result = await session.execute(
        select(Transaction).where(
            Transaction.workspace_id == transaction.workspace_id,
            Transaction.account_id == transaction.account_id,
            Transaction.fingerprint == transaction.fingerprint,
            Transaction.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


@router.post("/{import_batch_id}/confirm", response_model=ImportConfirmResult)
async def confirm_import_batch(
    workspace_id: UUID, import_batch_id: UUID, session: SessionDep
) -> ImportConfirmResult:
    batch = await _get_import_batch(session, workspace_id, import_batch_id)
    if batch.status != "parsed":
        raise HTTPException(
            status_code=422,
            detail="Only parsed import batches can be confirmed",
        )
    row_result = await session.execute(
        select(ImportRow)
        .where(
            ImportRow.import_batch_id == import_batch_id,
            ImportRow.workspace_id == workspace_id,
            ImportRow.status == "pending",
        )
        .order_by(ImportRow.row_number)
    )
    rows = list(row_result.scalars().all())
    if batch.account_id is None:
        raise HTTPException(
            status_code=422, detail="Import batch has no target account"
        )
    account = await _get_workspace_account(
        session, batch.workspace_id, batch.account_id
    )

    transaction_ids: list[UUID] = []
    imported_count = 0
    duplicate_count = 0
    error_count = 0
    try:
        for row in rows:
            try:
                transaction = _transaction_from_import(batch, row, account)
                await _ensure_category_in_workspace(
                    session, workspace_id, transaction.category_id
                )
                existing = await _find_existing_transaction(session, transaction)
                if existing is not None:
                    row.status = "duplicate"
                    duplicate_count += 1
                    continue
                session.add(transaction)
                row.transaction_id = transaction.id
                row.status = "imported"
                transaction_ids.append(transaction.id)
                imported_count += 1
            except HTTPException as exc:
                row.status = "error"
                row.error_message = str(exc.detail)
                error_count += 1
        batch.imported_count = (batch.imported_count or 0) + imported_count
        batch.duplicate_count = (batch.duplicate_count or 0) + duplicate_count
        batch.error_count = (batch.error_count or 0) + error_count
        batch.status = "processed" if error_count == 0 else "partially_processed"
        batch.processed_at = _now()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _conflict(exc) from exc
    return ImportConfirmResult(
        import_batch_id=batch.id,
        imported_count=imported_count,
        duplicate_count=duplicate_count,
        error_count=error_count,
        transaction_ids=transaction_ids,
    )
