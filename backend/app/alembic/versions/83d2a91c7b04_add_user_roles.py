"""Store one canonical user role; retain existing administrator privileges."""

from alembic import op
import sqlalchemy as sa

revision = "83d2a91c7b04"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user", sa.Column("role", sa.String(7), nullable=False, server_default="member")
    )
    op.execute(
        """UPDATE "user" SET role = CASE WHEN is_superuser THEN 'admin' ELSE 'member' END"""
    )
    op.create_check_constraint(
        "user_role", "user", "role IN ('admin', 'manager', 'member')"
    )
    op.drop_column("user", "is_superuser")


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute("""UPDATE "user" SET is_superuser = (role = 'admin')""")
    op.drop_constraint("user_role", "user", type_="check")
    op.drop_column("user", "role")
