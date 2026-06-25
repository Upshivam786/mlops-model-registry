"""add model_cards and dataset_links tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── model_cards ──────────────────────────────────────────────────────────
    op.create_table(
        'model_cards',
        sa.Column('id',                           sa.Integer(),  nullable=False),
        sa.Column('version_id',                   sa.Integer(),  nullable=False),
        sa.Column('intended_use',                 sa.Text(),     nullable=True),
        sa.Column('limitations',                  sa.Text(),     nullable=True),
        sa.Column('ethical_considerations',       sa.Text(),     nullable=True),
        sa.Column('training_data_summary',        sa.Text(),     nullable=True),
        sa.Column('evaluation_summary',           sa.Text(),     nullable=True),
        sa.Column('caveats_and_recommendations',  sa.Text(),     nullable=True),
        sa.Column('created_by',                   sa.String(100), nullable=False),
        sa.Column('created_at',                   sa.DateTime(), nullable=False),
        sa.Column('updated_at',                    sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['version_id'], ['model_versions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id'),
    )
    op.create_index(op.f('ix_model_cards_id'), 'model_cards', ['id'], unique=False)

    # ── dataset_links ────────────────────────────────────────────────────────
    op.create_table(
        'dataset_links',
        sa.Column('id',           sa.Integer(),    nullable=False),
        sa.Column('version_id',   sa.Integer(),    nullable=False),
        sa.Column('dataset_name', sa.String(255),  nullable=False),
        sa.Column('dataset_hash', sa.String(255),  nullable=False),
        sa.Column('dataset_uri',  sa.String(500),  nullable=True),
        sa.Column('role',         sa.String(50),   nullable=False),
        sa.Column('row_count',    sa.Integer(),    nullable=True),
        sa.Column('notes',        sa.Text(),       nullable=True),
        sa.Column('linked_by',    sa.String(100),  nullable=False),
        sa.Column('created_at',   sa.DateTime(),   nullable=False),
        sa.ForeignKeyConstraint(['version_id'], ['model_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_dataset_links_id'),           'dataset_links', ['id'],           unique=False)
    op.create_index(op.f('ix_dataset_links_version_id'),   'dataset_links', ['version_id'],   unique=False)
    op.create_index(op.f('ix_dataset_links_dataset_hash'), 'dataset_links', ['dataset_hash'], unique=False)
    op.create_index(op.f('ix_dataset_links_created_at'),   'dataset_links', ['created_at'],   unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dataset_links_created_at'),   table_name='dataset_links')
    op.drop_index(op.f('ix_dataset_links_dataset_hash'), table_name='dataset_links')
    op.drop_index(op.f('ix_dataset_links_version_id'),   table_name='dataset_links')
    op.drop_index(op.f('ix_dataset_links_id'),           table_name='dataset_links')
    op.drop_table('dataset_links')

    op.drop_index(op.f('ix_model_cards_id'), table_name='model_cards')
    op.drop_table('model_cards')
