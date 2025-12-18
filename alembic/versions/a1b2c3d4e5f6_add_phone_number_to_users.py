"""add phone_number to users

Revision ID: a1b2c3d4e5f6
Revises: 920638ae8f20
Create Date: 2025-12-17 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '920638ae8f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add phone_number column to users table."""
    op.add_column('users', sa.Column('phone_number', sa.String(), nullable=True), schema='testdb')


def downgrade() -> None:
    """Remove phone_number column from users table."""
    op.drop_column('users', 'phone_number', schema='testdb')

