"""create conversation_events table

Revision ID: 42c71e69b341
Revises: 2c1482a5811c
Create Date: 2025-12-01 10:11:22.845304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42c71e69b341'
down_revision: Union[str, Sequence[str], None] = '2c1482a5811c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
