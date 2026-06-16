"""add audit_logs table

Revision ID: a1b2c3d4e5f6
Revises: 43aa7442684c
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '43aa7442684c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id',            sa.Integer(),     nullable=False),
        sa.Column('user_id',       sa.Integer(),     nullable=False),
        sa.Column('username',      sa.String(100),   nullable=False),
        sa.Column('action',        sa.String(50),    nullable=False),
        sa.Column('resource_type', sa.String(50),    nullable=False),
        sa.Column('resource_id',   sa.Integer(),     nullable=False),
        sa.Column('old_value',     sa.Text(),        nullable=True),
        sa.Column('new_value',     sa.Text(),        nullable=True),
        sa.Column('timestamp',     sa.DateTime(),    nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_id'),        'audit_logs', ['id'],        unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_timestamp'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'),        table_name='audit_logs')
    op.drop_table('audit_logs')
