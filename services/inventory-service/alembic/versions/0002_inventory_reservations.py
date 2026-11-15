"""Create inventory reservations."""

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inventory_id"], ["inventories.id"]),
        sa.UniqueConstraint(
            "order_id", "inventory_id", name="uq_inventory_reservations_order_inventory"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_reservations_quantity"),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'RELEASED', 'CONFIRMED')",
            name="ck_inventory_reservations_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("inventory_reservations")
