import uuid
from sqlalchemy import Column, String, Numeric, Boolean, Text, ForeignKey, Date, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    txn_id = Column(String(100), nullable=True)
    date = Column(Date, nullable=True)
    merchant = Column(String(255), nullable=True)
    amount = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(10), nullable=True)
    status = Column(String(50), nullable=True)
    category = Column(String(100), nullable=True)
    account_id = Column(String(100), nullable=True)
    
    is_anomaly = Column(Boolean, default=False, nullable=False)
    anomaly_reason = Column(Text, nullable=True)
    llm_category = Column(String(100), nullable=True)
    llm_raw_response = Column(Text, nullable=True)
    llm_failed = Column(Boolean, default=False, nullable=False)

    job = relationship("Job", back_populates="transactions")

# Indexes as specified: job_id, account_id, merchant, is_anomaly, status
Index("ix_transactions_job_id", Transaction.job_id)
Index("ix_transactions_account_id", Transaction.account_id)
Index("ix_transactions_merchant", Transaction.merchant)
Index("ix_transactions_is_anomaly", Transaction.is_anomaly)
Index("ix_transactions_status", Transaction.status)
Index("ix_transactions_date", Transaction.date)
