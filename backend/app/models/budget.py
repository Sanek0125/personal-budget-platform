import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.currency import Currency
    from app.models.workspace import Workspace


class Budget(Base):
    """Workspace-scoped budget for a financial period."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("period_type in ('monthly')", name="ck_budgets_period_type"),
        CheckConstraint("period_end >= period_start", name="ck_budgets_period_dates"),
        Index(
            "ix_budgets_workspace_period", "workspace_id", "period_start", "period_end"
        ),
        Index("ix_budgets_currency_code", "currency_code"),
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
    name: Mapped[str] = mapped_column(Text)
    period_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="monthly", server_default="monthly"
    )
    period_start: Mapped[date]
    period_end: Mapped[date]
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
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

    workspace: Mapped["Workspace"] = relationship()
    currency: Mapped["Currency"] = relationship()
    limits: Mapped[list["BudgetLimit"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class BudgetLimit(Base):
    """Category limit inside a budget."""

    __tablename__ = "budget_limits"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_budget_limits_amount_positive"),
        UniqueConstraint(
            "budget_id", "category_id", name="uq_budget_limits_budget_category"
        ),
        Index("ix_budget_limits_budget_id", "budget_id"),
        Index("ix_budget_limits_category_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    rollover: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
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

    budget: Mapped[Budget] = relationship(back_populates="limits")
    category: Mapped["Category"] = relationship()
    currency: Mapped["Currency"] = relationship()
