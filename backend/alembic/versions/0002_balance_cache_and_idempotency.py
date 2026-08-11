"""add Member.net_balance and Expense.idempotency_key

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08

- Member.net_balance: cached running balance (paid - share), maintained on
  every expense write instead of recomputed by summing all expenses on read.
  Backfilled from existing expense/expense_share rows so upgrading an
  existing DB doesn't reset everyone's balance to zero.
- Expense.idempotency_key + a unique (trip_id, idempotency_key) constraint:
  lets the API dedupe retried/double-clicked "add expense" submits.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default lets this ADD COLUMN succeed on both SQLite and Postgres
    # even with existing rows (SQLite can't ALTER COLUMN to drop it afterward,
    # so it's left in place — harmless, since new rows go through the model's
    # Python-side default of 0.0 the same way).
    # batch_alter_table is used throughout so this file works unchanged on
    # both SQLite (which can't ALTER most constraints in place) and Postgres.
    with op.batch_alter_table("members") as batch_op:
        batch_op.add_column(
            sa.Column("net_balance", sa.Float(), nullable=False, server_default="0.0")
        )

    # Backfill net_balance for any members that already have expense history,
    # so this migration is safe to run against a populated database. Uses
    # correlated subqueries, which both SQLite and Postgres support the same way.
    op.execute(
        """
        UPDATE members
        SET net_balance = (
            SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE paid_by_id = members.id
        ) - (
            SELECT COALESCE(SUM(amount), 0) FROM expense_shares WHERE member_id = members.id
        )
        """
    )

    with op.batch_alter_table("expenses") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_expense_trip_idempotency_key", ["trip_id", "idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("expenses") as batch_op:
        batch_op.drop_constraint("uq_expense_trip_idempotency_key", type_="unique")
        batch_op.drop_column("idempotency_key")

    with op.batch_alter_table("members") as batch_op:
        batch_op.drop_column("net_balance")
