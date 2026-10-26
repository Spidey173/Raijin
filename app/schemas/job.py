from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class JobBase(BaseModel):
    filename: str

class JobCreate(JobBase):
    pass

class JobSummaryStats(BaseModel):
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    total_spend_inr: float
    total_spend_usd: float
    anomaly_count: int
    risk_level: str

class JobStatusResponse(BaseModel):
    job_id: UUID
    owner_id: Optional[str] = None
    status: str
    progress: str  # e.g., "0%", "100%", or steps
    created_at: datetime
    completed_at: Optional[datetime] = None
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    error_message: Optional[str] = None
    summary: Optional[JobSummaryStats] = None

    model_config = {
        "from_attributes": True
    }

class JobListItem(BaseModel):
    id: UUID
    owner_id: Optional[str] = None
    filename: str
    status: str
    row_count_raw: Optional[int] = None
    row_count_clean: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class PaginationMetadata(BaseModel):
    total: int
    page: int
    size: int
    pages: int

class JobListResponse(BaseModel):
    jobs: List[JobListItem]
    metadata: PaginationMetadata
