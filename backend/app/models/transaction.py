import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.currency import Currency
    from app.models.exchange_rate import ExchangeRate
    from app.models.user import User
    from app.models.workspace import Workspace


class Transaction(Base):
    """Workspace-scoped financial ledger row."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type in ('expense', 'income', 'transfer', 'adjustment')",
            name="ck_transactions_type",
        ),
        CheckConstraint(
            "status in ('posted', 'pending', 'deleted', 'duplicate', 'ignored')",
            name="ck_transactions_status",
        ),
        CheckConstraint(
            "source in ('manual', 'csv_import', 'excel_import', "
            "'pdf_import', 'telegram', 'api')",
            name="ck_transactions_source",
        ),
        CheckConstraint(
            "type != 'expense' OR amount < 0", name="ck_transactions_expense_negative"
        ),
        CheckConstraint(
            "type != 'income' OR amount > 0", name="ck_transactions_income_positive"
        ),
        CheckConstraint(
            "type != 'transfer' OR amount != 0", name="ck_transactions_transfer_nonzero"
        ),
        CheckConstraint(
            "type != 'adjustment' OR amount != 0",
            name="ck_transactions_adjustment_nonzero",
        ),
        Index(
            "uq_transactions_active_fingerprint",
            "workspace_id",
            "account_id",
            "fingerprint",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_transactions_workspace_occurred_at",
            "workspace_id",
            text("occurred_at DESC"),
        ),
        Index(
            "ix_transactions_account_occurred_at",
            "account_id",
            text("occurred_at DESC"),
        ),
        Index("ix_transactions_category_id", "category_id"),
        Index("ix_transactions_status", "status"),
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
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="posted", server_default="posted"
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booked_at: Mapped[date | None]
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    original_currency_code: Mapped[str | None] = mapped_column(
        ForeignKey("currencies.code")
    )
    base_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    base_currency_code: Mapped[str | None] = mapped_column(
        ForeignKey("currencies.code")
    )
    exchange_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exchange_rates.id")
    )
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    description: Mapped[str] = mapped_column(Text)
    merchant_name: Mapped[str | None] = mapped_column(Text)
    merchant_raw: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    category_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    categorized_by: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        Text, nullable=False, default="manual", server_default="manual"
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL")
    )
    import_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_rows.id", ondelete="SET NULL")
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped["Workspace"] = relationship()
    account: Mapped["Account"] = relationship()
    user: Mapped["User | None"] = relationship()
    category: Mapped["Category | None"] = relationship()
    currency: Mapped["Currency"] = relationship(foreign_keys=[currency_code])
    original_currency: Mapped["Currency | None"] = relationship(
        foreign_keys=[original_currency_code]
    )
    base_currency: Mapped["Currency | None"] = relationship(
        foreign_keys=[base_currency_code]
    )
    exchange_rate_snapshot: Mapped["ExchangeRate | None"] = relationship(
        foreign_keys=[exchange_rate_id]
    )
    splits: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class TransactionSplit(Base):
    """Categorized portion of a transaction."""

    __tablename__ = "transaction_splits"
    __table_args__ = (
        CheckConstraint("amount != 0", name="ck_transaction_splits_amount_nonzero"),
        Index("ix_transaction_splits_transaction_id", "transaction_id"),
        Index("ix_transaction_splits_category_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    transaction: Mapped[Transaction] = relationship(back_populates="splits")
    category: Mapped["Category"] = relationship()
    currency: Mapped["Currency"] = relationship()


class TransactionLink(Base):
    """Relationship between two transaction rows, e.g. transfer pair."""

    __tablename__ = "transaction_links"
    __table_args__ = (
        CheckConstraint(
            "relation_type in ('transfer_pair', 'refund', 'cashback_for', "
            "'correction', 'duplicate_of', 'debt_payment_for')",
            name="ck_transaction_links_relation_type",
        ),
        CheckConstraint(
            "transaction_id <> linked_transaction_id",
            name="ck_transaction_links_not_self",
        ),
        UniqueConstraint(
            "transaction_id",
            "linked_transaction_id",
            "relation_type",
            name="uq_transaction_links_pair_type",
        ),
        Index("ix_transaction_links_workspace_id", "workspace_id"),
        Index("ix_transaction_links_transaction_id", "transaction_id"),
        Index("ix_transaction_links_linked_transaction_id", "linked_transaction_id"),
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
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    linked_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    relation_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    workspace: Mapped["Workspace"] = relationship()
    transaction: Mapped[Transaction] = relationship(foreign_keys=[transaction_id])
    linked_transaction: Mapped[Transaction] = relationship(
        foreign_keys=[linked_transaction_id]
    )
