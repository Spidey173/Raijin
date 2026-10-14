import uuid
from sqlalchemy import Column, String, Integer, Numeric, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class JobSummary(Base):
    __tablename__ = "job_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    total_spend_inr = Column(Numeric(15, 2), nullable=False)
    total_spend_usd = Column(Numeric(15, 2), nullable=False)
    top_merchants = Column(JSON, nullable=False)
    anomaly_count = Column(Integer, nullable=False)
    narrative = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=False)

    job = relationship("Job", back_populates="summary")
