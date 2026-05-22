import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.currency import Currency
    from app.models.transaction import Transaction
    from app.models.workspace import Workspace


class Contact(Base):
    """Workspace-scoped person or organization involved in debts."""

    __tablename__ = "contacts"
    __table_args__ = (
        Index("ix_contacts_workspace_display_name", "workspace_id", "display_name"),
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
    display_name: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspace: Mapped["Workspace"] = relationship()
    debts: Mapped[list["Debt"]] = relationship(back_populates="contact")


class Debt(Base):
    """Money owed between the user and a contact."""

    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint(
            "direction in ('they_owe_me', 'i_owe_them')", name="ck_debts_direction"
        ),
        CheckConstraint(
            "status in ('open', 'partially_paid', 'paid', 'cancelled')",
            name="ck_debts_status",
        ),
        CheckConstraint(
            "principal_amount > 0", name="ck_debts_principal_amount_positive"
        ),
        Index("ix_debts_workspace_status", "workspace_id", "status"),
        Index("ix_debts_contact_id", "contact_id"),
        Index("ix_debts_source_transaction_id", "source_transaction_id"),
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
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="RESTRICT")
    )
    direction: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="open", server_default="open"
    )
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    description: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date | None]
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspace: Mapped["Workspace"] = relationship()
    contact: Mapped[Contact] = relationship(back_populates="debts")
    currency: Mapped["Currency"] = relationship()
    source_transaction: Mapped["Transaction | None"] = relationship(
        foreign_keys=[source_transaction_id]
    )
    payments: Mapped[list["DebtPayment"]] = relationship(
        back_populates="debt", cascade="all, delete-orphan"
    )


class DebtPayment(Base):
    """Repayment recorded against a debt."""

    __tablename__ = "debt_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_debt_payments_amount_positive"),
        Index("ix_debt_payments_debt_id", "debt_id"),
        Index("ix_debt_payments_transaction_id", "transaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    debt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("debts.id", ondelete="CASCADE")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    debt: Mapped[Debt] = relationship(back_populates="payments")
    currency: Mapped["Currency"] = relationship()
    transaction: Mapped["Transaction | None"] = relationship(
        foreign_keys=[transaction_id]
    )
