"""add compliance tables

Revision ID: 52db74776eb9
Revises: 37abcd61920c
Create Date: 2025-12-01 16:47:29.958963

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52db74776eb9'
down_revision: Union[str, Sequence[str], None] = '8848a5f9e175'
# down_revision: Union[str, Sequence[str], None] = '37abcd61920c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

policyset_status_enum = sa.Enum(
    'draft', 'active', 'archived',
    name='policysetstatus',
    schema='public',
    create_type=False
)

rule_type_enum = sa.Enum(
    'do', 'dont',
    name='ruletype',
    schema='public',
    create_type=False
)

severity_enum = sa.Enum(
    'info', 'low', 'medium', 'high', 'critical',
    name='severity',
    schema='public',
    create_type=False
)


def upgrade() -> None:
    op.create_table(
        'compliance_policy_sets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', policyset_status_enum, nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('ghostagent.users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        schema='ghostagent'
    )

    op.create_table(
        'compliance_policy_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_set_id', sa.Integer(), sa.ForeignKey('ghostagent.compliance_policy_sets.id')),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('ghostagent.users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='ghostagent'
    )

    op.create_table(
        'compliance_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('policy_set_id', sa.Integer(),
                  sa.ForeignKey('ghostagent.compliance_policy_sets.id', ondelete='CASCADE')),
        sa.Column('category', sa.String()),
        sa.Column('rule_type', rule_type_enum),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('severity', severity_enum),
        sa.Column('enabled', sa.Boolean()),
        sa.Column('ai_generated', sa.Boolean()),
        sa.Column('example_snippets', sa.JSON()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('ghostagent.users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='ghostagent'
    )


def downgrade() -> None:
    op.drop_table('compliance_rules', schema='ghostagent')
    op.drop_table('compliance_policy_documents', schema='ghostagent')
    op.drop_table('compliance_policy_sets', schema='ghostagent')