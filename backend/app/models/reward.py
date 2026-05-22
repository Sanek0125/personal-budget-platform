import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.currency import Currency
    from app.models.transaction import Transaction
    from app.models.workspace import Workspace


class RewardProgram(Base):
    """Workspace-scoped cashback, points, or miles program."""

    __tablename__ = "reward_programs"
    __table_args__ = (
        CheckConstraint(
            "program_type in ('cashback', 'points', 'miles')",
            name="ck_reward_programs_type",
        ),
        CheckConstraint(
            "(program_type = 'cashback' AND currency_code IS NOT NULL) OR "
            "(program_type in ('points', 'miles') AND currency_code IS NULL)",
            name="ck_reward_programs_currency_consistency",
        ),
        Index("ix_reward_programs_workspace_id", "workspace_id"),
        Index("ix_reward_programs_workspace_active", "workspace_id", "is_active"),
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
    program_type: Mapped[str] = mapped_column(Text)
    currency_code: Mapped[str | None] = mapped_column(ForeignKey("currencies.code"))
    issuer_name: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
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
    currency: Mapped["Currency | None"] = relationship()
    events: Mapped[list["RewardEvent"]] = relationship(back_populates="program")
    cashback_rules: Mapped[list["CashbackRule"]] = relationship(
        back_populates="program"
    )


class RewardEvent(Base):
    """Reward ledger event, either money cashback or points/miles."""

    __tablename__ = "reward_events"
    __table_args__ = (
        CheckConstraint(
            "event_type in ('earned', 'redeemed', 'adjusted', 'expired')",
            name="ck_reward_events_type",
        ),
        CheckConstraint(
            "status in ('expected', 'posted', 'cancelled')",
            name="ck_reward_events_status",
        ),
        CheckConstraint(
            "reward_kind in ('cashback', 'points', 'miles')",
            name="ck_reward_events_kind",
        ),
        CheckConstraint("amount > 0", name="ck_reward_events_amount_positive"),
        CheckConstraint(
            "(reward_kind = 'cashback' AND currency_code IS NOT NULL) OR "
            "(reward_kind in ('points', 'miles') AND currency_code IS NULL)",
            name="ck_reward_events_currency_consistency",
        ),
        Index(
            "ix_reward_events_workspace_occurred_at",
            "workspace_id",
            text("occurred_at DESC"),
        ),
        Index("ix_reward_events_program_id", "program_id"),
        Index("ix_reward_events_source_transaction_id", "source_transaction_id"),
        Index("ix_reward_events_reward_transaction_id", "reward_transaction_id"),
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
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reward_programs.id", ondelete="CASCADE")
    )
    cashback_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cashback_rules.id", ondelete="SET NULL")
    )
    source_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    reward_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="posted", server_default="posted"
    )
    reward_kind: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency_code: Mapped[str | None] = mapped_column(ForeignKey("currencies.code"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text)
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
    program: Mapped[RewardProgram] = relationship(back_populates="events")
    cashback_rule: Mapped["CashbackRule | None"] = relationship(back_populates="events")
    source_transaction: Mapped["Transaction | None"] = relationship(
        foreign_keys=[source_transaction_id]
    )
    reward_transaction: Mapped["Transaction | None"] = relationship(
        foreign_keys=[reward_transaction_id]
    )
    currency: Mapped["Currency | None"] = relationship()


class CashbackRule(Base):
    """Expected reward calculation rule for a reward program."""

    __tablename__ = "cashback_rules"
    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_cashback_rules_rate_positive"),
        CheckConstraint(
            "min_spend_amount IS NULL OR min_spend_amount > 0",
            name="ck_cashback_rules_min_spend_positive",
        ),
        CheckConstraint(
            "max_reward_amount IS NULL OR max_reward_amount > 0",
            name="ck_cashback_rules_max_reward_positive",
        ),
        Index("ix_cashback_rules_workspace_program", "workspace_id", "program_id"),
        Index("ix_cashback_rules_category_id", "category_id"),
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
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reward_programs.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    spend_currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    merchant_pattern: Mapped[str | None] = mapped_column(Text)
    min_spend_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    max_reward_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
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
    program: Mapped[RewardProgram] = relationship(back_populates="cashback_rules")
    category: Mapped["Category | None"] = relationship()
    spend_currency: Mapped["Currency"] = relationship()
    events: Mapped[list[RewardEvent]] = relationship(back_populates="cashback_rule")
