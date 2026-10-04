"""Add creation timestamps to Python student groups."""

import sqlalchemy as sa
from alembic import op

revision = "0003_group_created_at"
down_revision = "0002_assignments_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("py_student_groups")}
    if "created_at" not in columns:
        op.add_column("py_student_groups", sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ))


def downgrade() -> None:
    op.drop_column("py_student_groups", "created_at")