"""add job progress column

Revision ID: 002_add_job_progress
Revises: 001_initial
Create Date: 2026-10-29 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_job_progress'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('jobs', sa.Column('progress', sa.String(length=20), server_default='0%', nullable=False))

def downgrade() -> None:
    op.drop_column('jobs', 'progress')

