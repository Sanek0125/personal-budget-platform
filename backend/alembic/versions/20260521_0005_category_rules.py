"""category rules

Revision ID: 20260521_0005
Revises: 20260521_0004
Create Date: 2026-05-21 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0005"
down_revision: str | None = "20260521_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column(
            "match_field", sa.Text(), nullable=False, server_default="description"
        ),
        sa.Column("pattern", sa.Text(), nullable=True),
        sa.Column("amount_min", sa.Numeric(20, 6), nullable=True),
        sa.Column("amount_max", sa.Numeric(20, 6), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
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
            ["category_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "operator in ('contains', 'equals', 'starts_with', "
            "'regex', 'amount_between')",
            name="ck_category_rules_operator",
        ),
        sa.CheckConstraint(
            "match_field in ('description', 'merchant_name', 'merchant_raw')",
            name="ck_category_rules_match_field",
        ),
        sa.CheckConstraint(
            "(operator = 'amount_between' "
            "AND (amount_min IS NOT NULL OR amount_max IS NOT NULL)) "
            "OR (operator <> 'amount_between' AND pattern IS NOT NULL)",
            name="ck_category_rules_definition",
        ),
    )
    op.create_index(
        "ix_category_rules_workspace_id", "category_rules", ["workspace_id"]
    )
    op.create_index(
        "ix_category_rules_category_id", "category_rules", ["category_id"]
    )

    op.create_table(
        "category_rule_matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("matched_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_rule_id"], ["category_rules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "category_rule_id",
            "transaction_id",
            name="uq_category_rule_matches_rule_transaction",
        ),
    )
    op.create_index(
        "ix_category_rule_matches_workspace_id",
        "category_rule_matches",
        ["workspace_id"],
    )
    op.create_index(
        "ix_category_rule_matches_category_rule_id",
        "category_rule_matches",
        ["category_rule_id"],
    )
    op.create_index(
        "ix_category_rule_matches_transaction_id",
        "category_rule_matches",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_category_rule_matches_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_category_rule_matches_category_rule_id")
    op.execute("DROP INDEX IF EXISTS ix_category_rule_matches_workspace_id")
    op.drop_table("category_rule_matches")
    op.execute("DROP INDEX IF EXISTS ix_category_rules_category_id")
    op.execute("DROP INDEX IF EXISTS ix_category_rules_workspace_id")
    op.drop_table("category_rules")
