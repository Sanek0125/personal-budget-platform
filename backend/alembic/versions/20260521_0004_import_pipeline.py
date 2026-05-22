"""csv import pipeline foundation

Revision ID: 20260521_0004
Revises: 20260521_0003
Create Date: 2026-05-21 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260521_0004"
down_revision: str | None = "20260521_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
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
            ["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("workspace_id", "sha256", name="uq_files_workspace_sha256"),
    )
    op.create_index("ix_files_workspace_id", "files", ["workspace_id"])

    op.create_table(
        "import_batches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="uploaded"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "source_type in ('csv', 'xlsx', 'pdf')",
            name="ck_import_batches_source_type",
        ),
        sa.CheckConstraint(
            "status in ('uploaded', 'parsed', 'processed', 'failed', "
            "'partially_processed')",
            name="ck_import_batches_status",
        ),
        sa.UniqueConstraint(
            "workspace_id", "file_hash", name="uq_import_batches_workspace_file_hash"
        ),
    )
    op.create_index(
        "ix_import_batches_workspace_id", "import_batches", ["workspace_id"]
    )
    op.create_index("ix_import_batches_status", "import_batches", ["status"])

    op.create_table(
        "import_rows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_data", postgresql.JSONB(), nullable=True),
        sa.Column("raw_hash", sa.Text(), nullable=False),
        sa.Column("normalized_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status in ('pending', 'imported', 'duplicate', "
            "'possible_duplicate', 'ignored', 'error')",
            name="ck_import_rows_status",
        ),
        sa.UniqueConstraint(
            "import_batch_id", "row_number", name="uq_import_rows_batch_row_number"
        ),
    )
    op.create_index("ix_import_rows_batch_id", "import_rows", ["import_batch_id"])
    op.create_index("ix_import_rows_workspace_id", "import_rows", ["workspace_id"])
    op.create_index("ix_import_rows_status", "import_rows", ["status"])

    op.add_column(
        "transactions",
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("import_row_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transactions_import_batch_id",
        "transactions",
        "import_batches",
        ["import_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_transactions_import_row_id",
        "transactions",
        "import_rows",
        ["import_row_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "duplicate_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "existing_transaction_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("similarity_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["import_row_id"], ["import_rows.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["existing_transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status in ('pending', 'confirmed_duplicate', 'not_duplicate')",
            name="ck_duplicate_candidates_status",
        ),
    )
    op.create_index(
        "ix_duplicate_candidates_workspace_id", "duplicate_candidates", ["workspace_id"]
    )
    op.create_index(
        "ix_duplicate_candidates_import_row_id",
        "duplicate_candidates",
        ["import_row_id"],
    )
    op.create_index(
        "ix_duplicate_candidates_existing_transaction_id",
        "duplicate_candidates",
        ["existing_transaction_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_duplicate_candidates_existing_transaction_id")
    op.execute("DROP INDEX IF EXISTS ix_duplicate_candidates_import_row_id")
    op.execute("DROP INDEX IF EXISTS ix_duplicate_candidates_workspace_id")
    op.drop_table("duplicate_candidates")
    op.drop_constraint(
        "fk_transactions_import_row_id", "transactions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_transactions_import_batch_id", "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "import_row_id")
    op.drop_column("transactions", "import_batch_id")
    op.execute("DROP INDEX IF EXISTS ix_import_rows_status")
    op.execute("DROP INDEX IF EXISTS ix_import_rows_workspace_id")
    op.execute("DROP INDEX IF EXISTS ix_import_rows_batch_id")
    op.drop_table("import_rows")
    op.execute("DROP INDEX IF EXISTS ix_import_batches_status")
    op.execute("DROP INDEX IF EXISTS ix_import_batches_workspace_id")
    op.drop_table("import_batches")
    op.execute("DROP INDEX IF EXISTS ix_files_workspace_id")
    op.drop_table("files")
