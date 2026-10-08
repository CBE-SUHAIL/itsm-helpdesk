"""baseline: establish the migration chain

Revision ID: 20261008_2150_baseline
Revises:
Create Date: 2026-10-08

F05 creates the mechanism, not the tables. This revision therefore changes
nothing on purpose. It exists so the chain has a root, so that
"alembic upgrade head" can be proven against the running container before
anything depends on it, and so every later revision is a plain addition.

Tables arrive with D01-D06, and refresh_tokens with A01/A02. docs/DATA_MODEL.md
records which row owns which table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20261008_2150_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create nothing. The chain starts here."""
    pass


def downgrade() -> None:
    """Create nothing. The chain starts here."""
    pass
