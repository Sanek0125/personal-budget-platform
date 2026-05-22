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
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.transaction import Transaction
    from app.models.workspace import Workspace


class CategoryRule(Base):
    """Workspace-scoped rule that auto-assigns a category to transactions."""

    __tablename__ = "category_rules"
    __table_args__ = (
        CheckConstraint(
            "operator in ('contains', 'equals', 'starts_with', "
            "'regex', 'amount_between')",
            name="ck_category_rules_operator",
        ),
        CheckConstraint(
            "match_field in ('description', 'merchant_name', 'merchant_raw')",
            name="ck_category_rules_match_field",
        ),
        CheckConstraint(
            "(operator = 'amount_between' "
            "AND (amount_min IS NOT NULL OR amount_max IS NOT NULL)) "
            "OR (operator <> 'amount_between' AND pattern IS NOT NULL)",
            name="ck_category_rules_definition",
        ),
        Index("ix_category_rules_workspace_id", "workspace_id"),
        Index("ix_category_rules_category_id", "category_id"),
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
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    operator: Mapped[str] = mapped_column(Text)
    match_field: Mapped[str] = mapped_column(
        Text, nullable=False, default="description", server_default="description"
    )
    pattern: Mapped[str | None] = mapped_column(Text)
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
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
    category: Mapped["Category"] = relationship()
    matches: Mapped[list["CategoryRuleMatch"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class CategoryRuleMatch(Base):
    """Audit row recording a rule that categorized a transaction."""

    __tablename__ = "category_rule_matches"
    __table_args__ = (
        UniqueConstraint(
            "category_rule_id",
            "transaction_id",
            name="uq_category_rule_matches_rule_transaction",
        ),
        Index("ix_category_rule_matches_workspace_id", "workspace_id"),
        Index("ix_category_rule_matches_category_rule_id", "category_rule_id"),
        Index("ix_category_rule_matches_transaction_id", "transaction_id"),
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
    category_rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("category_rules.id", ondelete="CASCADE")
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE")
    )
    matched_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    workspace: Mapped["Workspace"] = relationship()
    rule: Mapped[CategoryRule] = relationship(back_populates="matches")
    transaction: Mapped["Transaction"] = relationship()
