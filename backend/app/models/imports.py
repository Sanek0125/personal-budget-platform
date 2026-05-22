import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.transaction import Transaction
    from app.models.user import User
    from app.models.workspace import Workspace


class File(Base):
    """Uploaded source file metadata for import batches."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_files_workspace_sha256"),
        Index("ix_files_workspace_id", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    original_filename: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    workspace: Mapped["Workspace"] = relationship()
    uploaded_by_user: Mapped["User"] = relationship()


class ImportBatch(Base):
    """A parsed uploaded statement awaiting confirmation."""

    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "file_hash", name="uq_import_batches_workspace_file_hash"
        ),
        CheckConstraint(
            "source_type in ('csv', 'xlsx', 'pdf')",
            name="ck_import_batches_source_type",
        ),
        CheckConstraint(
            "status in ('uploaded', 'parsed', 'processed', 'failed', "
            "'partially_processed')",
            name="ck_import_batches_status",
        ),
        Index("ix_import_batches_workspace_id", "workspace_id"),
        Index("ix_import_batches_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL")
    )
    source_type: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="uploaded", server_default="uploaded"
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    imported_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    parser_version: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped["Workspace"] = relationship()
    user: Mapped["User"] = relationship()
    account: Mapped["Account | None"] = relationship()
    file: Mapped["File | None"] = relationship()
    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class ImportRow(Base):
    """One raw and normalized row within an import batch."""

    __tablename__ = "import_rows"
    __table_args__ = (
        UniqueConstraint(
            "import_batch_id", "row_number", name="uq_import_rows_batch_row_number"
        ),
        CheckConstraint(
            "status in ('pending', 'imported', 'duplicate', "
            "'possible_duplicate', 'ignored', 'error')",
            name="ck_import_rows_status",
        ),
        Index("ix_import_rows_batch_id", "import_batch_id"),
        Index("ix_import_rows_workspace_id", "workspace_id"),
        Index("ix_import_rows_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    normalized_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_hash: Mapped[str] = mapped_column(Text)
    normalized_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")
    workspace: Mapped["Workspace"] = relationship()
    transaction: Mapped["Transaction | None"] = relationship(
        foreign_keys=[transaction_id]
    )


class DuplicateCandidate(Base):
    """Possible duplicate relation requiring user resolution."""

    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'confirmed_duplicate', 'not_duplicate')",
            name="ck_duplicate_candidates_status",
        ),
        Index("ix_duplicate_candidates_workspace_id", "workspace_id"),
        Index("ix_duplicate_candidates_import_row_id", "import_row_id"),
        Index(
            "ix_duplicate_candidates_existing_transaction_id", "existing_transaction_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    import_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_rows.id", ondelete="CASCADE")
    )
    existing_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    similarity_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped["Workspace"] = relationship()
    import_row: Mapped[ImportRow] = relationship()
    existing_transaction: Mapped["Transaction"] = relationship(
        foreign_keys=[existing_transaction_id]
    )
