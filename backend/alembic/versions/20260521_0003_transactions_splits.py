"""transactions and splits

Revision ID: 20260521_0003
Revises: 20260521_0002
Create Date: 2026-05-21 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0003"
down_revision: str | None = "20260521_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="posted"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_at", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("original_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("original_currency_code", sa.String(length=3), nullable=True),
        sa.Column("base_amount", sa.Numeric(20, 6), nullable=True),
        sa.Column("base_currency_code", sa.String(length=3), nullable=True),
        sa.Column("exchange_rate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(24, 12), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("merchant_name", sa.Text(), nullable=True),
        sa.Column("merchant_raw", sa.Text(), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("categorized_by", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["original_currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["base_currency_code"], ["currencies.code"]),
        sa.ForeignKeyConstraint(["exchange_rate_id"], ["exchange_rates.id"]),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "type in ('expense', 'income', 'transfer', 'adjustment')",
            name="ck_transactions_type",
        ),
        sa.CheckConstraint(
            "status in ('posted', 'pending', 'deleted', 'duplicate', 'ignored')",
            name="ck_transactions_status",
        ),
        sa.CheckConstraint(
            "source in ('manual', 'csv_import', 'excel_import', "
            "'pdf_import', 'telegram', 'api')",
            name="ck_transactions_source",
        ),
        sa.CheckConstraint(
            "type != 'expense' OR amount < 0", name="ck_transactions_expense_negative"
        ),
        sa.CheckConstraint(
            "type != 'income' OR amount > 0", name="ck_transactions_income_positive"
        ),
        sa.CheckConstraint(
            "type != 'transfer' OR amount != 0", name="ck_transactions_transfer_nonzero"
        ),
        sa.CheckConstraint(
            "type != 'adjustment' OR amount != 0",
            name="ck_transactions_adjustment_nonzero",
        ),
    )
    op.create_index(
        "uq_transactions_active_fingerprint",
        "transactions",
        ["workspace_id", "account_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_transactions_workspace_occurred_at",
        "transactions",
        ["workspace_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_transactions_account_occurred_at",
        "transactions",
        ["account_id", sa.text("occurred_at DESC")],
    )
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])

    op.create_table(
        "transaction_splits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["currency_code"], ["currencies.code"]),
        sa.CheckConstraint("amount != 0", name="ck_transaction_splits_amount_nonzero"),
    )
    op.create_index(
        "ix_transaction_splits_transaction_id", "transaction_splits", ["transaction_id"]
    )
    op.create_index(
        "ix_transaction_splits_category_id", "transaction_splits", ["category_id"]
    )

    op.create_table(
        "transaction_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "linked_transaction_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("relation_type", sa.Text(), nullable=False),
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
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["linked_transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "transaction_id",
            "linked_transaction_id",
            "relation_type",
            name="uq_transaction_links_pair_type",
        ),
        sa.CheckConstraint(
            "relation_type in ('transfer_pair', 'refund', 'cashback_for', "
            "'correction', 'duplicate_of', 'debt_payment_for')",
            name="ck_transaction_links_relation_type",
        ),
        sa.CheckConstraint(
            "transaction_id <> linked_transaction_id",
            name="ck_transaction_links_not_self",
        ),
    )
    op.create_index(
        "ix_transaction_links_workspace_id", "transaction_links", ["workspace_id"]
    )
    op.create_index(
        "ix_transaction_links_transaction_id", "transaction_links", ["transaction_id"]
    )
    op.create_index(
        "ix_transaction_links_linked_transaction_id",
        "transaction_links",
        ["linked_transaction_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transaction_links_linked_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_transaction_links_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_transaction_links_workspace_id")
    op.drop_table("transaction_links")
    op.execute("DROP INDEX IF EXISTS ix_transaction_splits_category_id")
    op.execute("DROP INDEX IF EXISTS ix_transaction_splits_transaction_id")
    op.drop_table("transaction_splits")
    op.execute("DROP INDEX IF EXISTS ix_transactions_status")
    op.execute("DROP INDEX IF EXISTS ix_transactions_category_id")
    op.execute("DROP INDEX IF EXISTS ix_transactions_account_occurred_at")
    op.execute("DROP INDEX IF EXISTS ix_transactions_workspace_occurred_at")
    op.execute("DROP INDEX IF EXISTS uq_transactions_active_fingerprint")
    op.drop_table("transactions")
