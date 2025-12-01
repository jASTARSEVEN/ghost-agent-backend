"""check_current_state

Revision ID: 7cc9dc1c9579
Revises: 42c71e69b341
Create Date: 2025-12-01 10:37:15.779480

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7cc9dc1c9579'
down_revision: Union[str, Sequence[str], None] = '42c71e69b341'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Only create conversation_events table - other tables already exist
    op.create_table('conversation_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('conversation_id', sa.String(), nullable=True),
    sa.Column('call_id', sa.String(), nullable=True),
    sa.Column('event_type', sa.String(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('received_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='ghostagent'
    )
    op.create_index('idx_user_conversation', 'conversation_events', ['user_id', 'conversation_id'], unique=False, schema='ghostagent')
    op.create_index(op.f('ix_ghostagent_conversation_events_call_id'), 'conversation_events', ['call_id'], unique=False, schema='ghostagent')
    op.create_index(op.f('ix_ghostagent_conversation_events_conversation_id'), 'conversation_events', ['conversation_id'], unique=False, schema='ghostagent')
    op.create_index(op.f('ix_ghostagent_conversation_events_received_at'), 'conversation_events', ['received_at'], unique=False, schema='ghostagent')
    op.create_index(op.f('ix_ghostagent_conversation_events_user_id'), 'conversation_events', ['user_id'], unique=False, schema='ghostagent')


def downgrade() -> None:
    """Downgrade schema."""
    # Only drop conversation_events table - other tables should remain
    op.drop_index(op.f('ix_ghostagent_conversation_events_user_id'), table_name='conversation_events', schema='ghostagent')
    op.drop_index(op.f('ix_ghostagent_conversation_events_received_at'), table_name='conversation_events', schema='ghostagent')
    op.drop_index(op.f('ix_ghostagent_conversation_events_conversation_id'), table_name='conversation_events', schema='ghostagent')
    op.drop_index(op.f('ix_ghostagent_conversation_events_call_id'), table_name='conversation_events', schema='ghostagent')
    op.drop_index('idx_user_conversation', table_name='conversation_events', schema='ghostagent')
    op.drop_table('conversation_events', schema='ghostagent')