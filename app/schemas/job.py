import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.job import JobStatus

class JobBase(BaseModel):
    pass

class JobCreate(JobBase):
    pass

class JobResponse(JobBase):
    id: uuid.UUID
    status: JobStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
