"""Add assignments and attempt snapshots."""

from alembic import op

from app import models  # noqa: F401
from app.database import Base

revision = "0002_assignments_attempts"
down_revision = "0001_python_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("py_attempt_questions", "py_attempts", "py_assignments"):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)