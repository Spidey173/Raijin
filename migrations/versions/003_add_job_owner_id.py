"""add job owner_id column

Revision ID: 003_add_job_owner_id
Revises: 002_add_job_progress
Create Date: 2026-10-29 21:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_add_job_owner_id'
down_revision: Union[str, None] = '002_add_job_progress'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('jobs', sa.Column('owner_id', sa.String(length=100), server_default='default-user', nullable=True))
    op.create_index(op.f('ix_jobs_owner_id'), 'jobs', ['owner_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_owner_id'), table_name='jobs')
    op.drop_column('jobs', 'owner_id')

