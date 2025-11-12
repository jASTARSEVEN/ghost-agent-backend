"""add conversation events table

Revision ID: a1b2c3d4e5f6
Revises: 37abcd61920c
Create Date: 2025-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '37abcd61920c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversation_events table in ghostagent schema
    op.create_table(
        'conversation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('call_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        schema='ghostagent',
    )

    # Indexes
    op.create_index('ix_ghostagent_conversation_events_user_id', 'conversation_events', ['user_id'], unique=False, schema='ghostagent')
    op.create_index('ix_ghostagent_conversation_events_conversation_id', 'conversation_events', ['conversation_id'], unique=False, schema='ghostagent')
    op.create_index('ix_ghostagent_conversation_events_received_at', 'conversation_events', ['received_at'], unique=False, schema='ghostagent')
    op.create_index('idx_user_conversation', 'conversation_events', ['user_id', 'conversation_id'], unique=False, schema='ghostagent')


def downgrade() -> None:
    op.drop_index('idx_user_conversation', table_name='conversation_events', schema='ghostagent')
    op.drop_index('ix_ghostagent_conversation_events_received_at', table_name='conversation_events', schema='ghostagent')
    op.drop_index('ix_ghostagent_conversation_events_conversation_id', table_name='conversation_events', schema='ghostagent')
    op.drop_index('ix_ghostagent_conversation_events_user_id', table_name='conversation_events', schema='ghostagent')
    op.drop_table('conversation_events', schema='ghostagent')

