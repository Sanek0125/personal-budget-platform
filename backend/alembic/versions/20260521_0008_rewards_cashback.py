"""rewards cashback

Revision ID: 20260521_0008
Revises: 20260521_0007
Create Date: 2026-05-21 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0008"
down_revision: str | None = "20260521_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reward_programs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("program_type", sa.Text(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.Column("issuer_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "program_type in ('cashback', 'points', 'miles')",
            name="ck_reward_programs_type",
        ),
        sa.CheckConstraint(
            "(program_type = 'cashback' AND currency_code IS NOT NULL) OR "
            "(program_type in ('points', 'miles') AND currency_code IS NULL)",
            name="ck_reward_programs_currency_consistency",
        ),
    )
    op.create_index(
        "ix_reward_programs_workspace_id", "reward_programs", ["workspace_id"]
    )
    op.create_index(
        "ix_reward_programs_workspace_active",
        "reward_programs",
        ["workspace_id", "is_active"],
    )

    op.create_table(
        "cashback_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("rate", sa.Numeric(20, 6), nullable=False),
        sa.Column("spend_currency_code", sa.String(length=3), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merchant_pattern", sa.Text(), nullable=True),
        sa.Column("min_spend_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("max_reward_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.ForeignKeyConstraint(
            ["program_id"], ["reward_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["spend_currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint("rate > 0", name="ck_cashback_rules_rate_positive"),
        sa.CheckConstraint(
            "min_spend_amount IS NULL OR min_spend_amount > 0",
            name="ck_cashback_rules_min_spend_positive",
        ),
        sa.CheckConstraint(
            "max_reward_amount IS NULL OR max_reward_amount > 0",
            name="ck_cashback_rules_max_reward_positive",
        ),
    )
    op.create_index(
        "ix_cashback_rules_workspace_program",
        "cashback_rules",
        ["workspace_id", "program_id"],
    )
    op.create_index("ix_cashback_rules_category_id", "cashback_rules", ["category_id"])

    op.create_table(
        "reward_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cashback_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "source_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "reward_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="posted"),
        sa.Column("reward_kind", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["program_id"], ["reward_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cashback_rule_id"], ["cashback_rules.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reward_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.CheckConstraint(
            "event_type in ('earned', 'redeemed', 'adjusted', 'expired')",
            name="ck_reward_events_type",
        ),
        sa.CheckConstraint(
            "status in ('expected', 'posted', 'cancelled')",
            name="ck_reward_events_status",
        ),
        sa.CheckConstraint(
            "reward_kind in ('cashback', 'points', 'miles')",
            name="ck_reward_events_kind",
        ),
        sa.CheckConstraint("amount > 0", name="ck_reward_events_amount_positive"),
        sa.CheckConstraint(
            "(reward_kind = 'cashback' AND currency_code IS NOT NULL) OR "
            "(reward_kind in ('points', 'miles') AND currency_code IS NULL)",
            name="ck_reward_events_currency_consistency",
        ),
    )
    op.create_index(
        "ix_reward_events_workspace_occurred_at",
        "reward_events",
        ["workspace_id", sa.text("occurred_at DESC")],
    )
    op.create_index("ix_reward_events_program_id", "reward_events", ["program_id"])
    op.create_index(
        "ix_reward_events_source_transaction_id",
        "reward_events",
        ["source_transaction_id"],
    )
    op.create_index(
        "ix_reward_events_reward_transaction_id",
        "reward_events",
        ["reward_transaction_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reward_events_reward_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_reward_events_source_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_reward_events_program_id")
    op.execute("DROP INDEX IF EXISTS ix_reward_events_workspace_occurred_at")
    op.drop_table("reward_events")
    op.execute("DROP INDEX IF EXISTS ix_cashback_rules_category_id")
    op.execute("DROP INDEX IF EXISTS ix_cashback_rules_workspace_program")
    op.drop_table("cashback_rules")
    op.execute("DROP INDEX IF EXISTS ix_reward_programs_workspace_active")
    op.execute("DROP INDEX IF EXISTS ix_reward_programs_workspace_id")
    op.drop_table("reward_programs")
