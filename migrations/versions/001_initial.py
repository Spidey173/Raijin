"""initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-09 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('row_count_raw', sa.Integer(), nullable=True),
        sa.Column('row_count_clean', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_id'), 'jobs', ['id'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('txn_id', sa.String(length=100), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('merchant', sa.String(length=255), nullable=True),
        sa.Column('amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('account_id', sa.String(length=100), nullable=True),
        sa.Column('is_anomaly', sa.Boolean(), nullable=False),
        sa.Column('anomaly_reason', sa.Text(), nullable=True),
        sa.Column('llm_category', sa.String(length=100), nullable=True),
        sa.Column('llm_raw_response', sa.Text(), nullable=True),
        sa.Column('llm_failed', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index('ix_transactions_job_id', 'transactions', ['job_id'], unique=False)
    op.create_index('ix_transactions_account_id', 'transactions', ['account_id'], unique=False)
    op.create_index('ix_transactions_merchant', 'transactions', ['merchant'], unique=False)
    op.create_index('ix_transactions_is_anomaly', 'transactions', ['is_anomaly'], unique=False)
    op.create_index('ix_transactions_status', 'transactions', ['status'], unique=False)
    op.create_index('ix_transactions_date', 'transactions', ['date'], unique=False)

    # Create job_summaries table
    op.create_table(
        'job_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_spend_inr', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_spend_usd', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('top_merchants', sa.JSON(), nullable=False),
        sa.Column('anomaly_count', sa.Integer(), nullable=False),
        sa.Column('narrative', sa.Text(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )
    op.create_index(op.f('ix_job_summaries_id'), 'job_summaries', ['id'], unique=False)
    op.create_index(op.f('ix_job_summaries_job_id'), 'job_summaries', ['job_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_job_summaries_job_id'), table_name='job_summaries')
    op.drop_index(op.f('ix_job_summaries_id'), table_name='job_summaries')
    op.drop_table('job_summaries')
    
    op.drop_index('ix_transactions_date', table_name='transactions')
    op.drop_index('ix_transactions_status', table_name='transactions')
    op.drop_index('ix_transactions_is_anomaly', table_name='transactions')
    op.drop_index('ix_transactions_merchant', table_name='transactions')
    op.drop_index('ix_transactions_account_id', table_name='transactions')
    op.drop_index('ix_transactions_job_id', table_name='transactions')
    op.drop_index(op.f('ix_transactions_id'), table_name='transactions')
    op.drop_table('transactions')
    
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_id'), table_name='jobs')
    op.drop_table('jobs')
