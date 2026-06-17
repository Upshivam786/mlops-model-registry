"""add training_runs table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'training_runs',
        sa.Column('id',                sa.Integer(),     nullable=False),
        sa.Column('version_id',        sa.Integer(),     nullable=False),
        sa.Column('dataset_name',      sa.String(255),   nullable=True),
        sa.Column('dataset_hash',      sa.String(255),   nullable=True),
        sa.Column('hyperparameters',   sa.Text(),        nullable=True),
        sa.Column('learning_rate',     sa.Float(),       nullable=True),
        sa.Column('epochs',            sa.Integer(),     nullable=True),
        sa.Column('batch_size',        sa.Integer(),     nullable=True),
        sa.Column('metrics',           sa.Text(),        nullable=True),
        sa.Column('accuracy',          sa.Float(),       nullable=True),
        sa.Column('f1_score',          sa.Float(),       nullable=True),
        sa.Column('loss',              sa.Float(),       nullable=True),
        sa.Column('framework',         sa.String(100),   nullable=True),
        sa.Column('framework_version', sa.String(50),    nullable=True),
        sa.Column('training_duration', sa.Integer(),     nullable=True),
        sa.Column('created_by',        sa.String(100),   nullable=False),
        sa.Column('created_at',        sa.DateTime(),    nullable=False),
        sa.ForeignKeyConstraint(['version_id'], ['model_versions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_id'),
    )
    op.create_index(op.f('ix_training_runs_id'),         'training_runs', ['id'],         unique=False)
    op.create_index(op.f('ix_training_runs_accuracy'),   'training_runs', ['accuracy'],   unique=False)
    op.create_index(op.f('ix_training_runs_f1_score'),   'training_runs', ['f1_score'],   unique=False)
    op.create_index(op.f('ix_training_runs_created_at'), 'training_runs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_training_runs_created_at'), table_name='training_runs')
    op.drop_index(op.f('ix_training_runs_f1_score'),   table_name='training_runs')
    op.drop_index(op.f('ix_training_runs_accuracy'),   table_name='training_runs')
    op.drop_index(op.f('ix_training_runs_id'),         table_name='training_runs')
    op.drop_table('training_runs')
