"""budgets

Revision ID: 20260521_0006
Revises: 20260521_0005
Create Date: 2026-05-21 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0006"
down_revision: str | None = "20260521_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("period_type", sa.Text(), nullable=False, server_default="monthly"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.CheckConstraint("period_type in ('monthly')", name="ck_budgets_period_type"),
        sa.CheckConstraint(
            "period_end >= period_start", name="ck_budgets_period_dates"
        ),
    )
    op.create_index(
        "ix_budgets_workspace_period",
        "budgets",
        ["workspace_id", "period_start", "period_end"],
    )
    op.create_index("ix_budgets_currency_code", "budgets", ["currency_code"])

    op.create_table(
        "budget_limits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("budget_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("rollover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.CheckConstraint("amount > 0", name="ck_budget_limits_amount_positive"),
        sa.UniqueConstraint(
            "budget_id", "category_id", name="uq_budget_limits_budget_category"
        ),
    )
    op.create_index("ix_budget_limits_budget_id", "budget_limits", ["budget_id"])
    op.create_index("ix_budget_limits_category_id", "budget_limits", ["category_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_budget_limits_category_id")
    op.execute("DROP INDEX IF EXISTS ix_budget_limits_budget_id")
    op.drop_table("budget_limits")
    op.execute("DROP INDEX IF EXISTS ix_budgets_currency_code")
    op.execute("DROP INDEX IF EXISTS ix_budgets_workspace_period")
    op.drop_table("budgets")
