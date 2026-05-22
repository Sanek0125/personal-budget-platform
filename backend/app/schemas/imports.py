from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.services.csv_imports import CsvColumnMapping

ImportBatchStatus = Literal[
    "uploaded", "parsed", "processed", "failed", "partially_processed"
]
ImportRowStatus = Literal[
    "pending", "imported", "duplicate", "possible_duplicate", "ignored", "error"
]


class CsvImportUpload(BaseModel):
    user_id: UUID
    account_id: UUID
    original_filename: str = Field(min_length=1)
    content: str = Field(min_length=1, max_length=5_000_000)
    column_mapping: CsvColumnMapping
    source_name: str | None = None

    @field_validator("original_filename")
    @classmethod
    def require_csv_filename(cls, value: str) -> str:
        value = value.strip()
        if not value.lower().endswith(".csv"):
            raise ValueError("CSV imports require a .csv filename")
        return value


class ImportBatchRead(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    account_id: UUID | None = None
    file_id: UUID | None = None
    source_type: str
    source_name: str | None = None
    original_filename: str
    file_hash: str
    file_size: int | None = None
    status: ImportBatchStatus
    total_rows: int
    imported_count: int
    duplicate_count: int
    error_count: int
    parser_version: str | None = None
    uploaded_at: datetime | None = None
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ImportRowRead(BaseModel):
    id: UUID
    import_batch_id: UUID
    workspace_id: UUID
    row_number: int
    raw_data: dict[str, Any]
    normalized_data: dict[str, Any] | None = None
    raw_hash: str
    normalized_hash: str | None = None
    status: ImportRowStatus
    error_message: str | None = None
    transaction_id: UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ImportConfirmResult(BaseModel):
    import_batch_id: UUID
    imported_count: int
    duplicate_count: int
    error_count: int
    transaction_ids: list[UUID]
