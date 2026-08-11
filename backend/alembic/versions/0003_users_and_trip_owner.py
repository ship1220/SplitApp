"""add users table and Trip.owner_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-08

Adds optional user accounts:
- users: id, email (unique), hashed_password, created_at
- trips.owner_id: nullable FK to users.id. NULL for anonymous/shared trips
  (the existing edit_token/view_token flow), set only when a trip is
  created while logged in. Existing trips are unaffected (owner_id backfills
  to NULL) and keep working exactly as before via their tokens.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    with op.batch_alter_table("trips") as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_trips_owner_id_users", "users", ["owner_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("trips") as batch_op:
        batch_op.drop_constraint("fk_trips_owner_id_users", type_="foreignkey")
        batch_op.drop_column("owner_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
