"""baseline schema (trips, members, expenses, expense_shares)

Revision ID: 0001
Revises:
Create Date: 2026-08-08

This mirrors the schema that `models.Base.metadata.create_all` previously
created directly. It intentionally does NOT include Member.net_balance or
Expense.idempotency_key — those are added in 0002_balance_cache_and_idempotency.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("edit_token", sa.String(), nullable=True),
        sa.Column("view_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_trips_edit_token", "trips", ["edit_token"], unique=True)
    op.create_index("ix_trips_view_token", "trips", ["view_token"], unique=True)

    op.create_table(
        "members",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("trip_id", sa.String(), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("trip_id", sa.String(), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("paid_by_id", sa.String(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column(
            "split_type",
            sa.Enum("equal", "percentage", "exact", name="splittype"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "expense_shares",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("expense_id", sa.String(), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("member_id", sa.String(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("expense_shares")
    op.drop_table("expenses")
    op.drop_table("members")
    op.drop_index("ix_trips_view_token", table_name="trips")
    op.drop_index("ix_trips_edit_token", table_name="trips")
    op.drop_table("trips")
    # Postgres leaves the enum type behind after dropping the column/table;
    # clean it up explicitly so downgrade is fully reversible.
    sa.Enum(name="splittype").drop(op.get_bind(), checkfirst=True)
