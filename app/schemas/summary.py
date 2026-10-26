from typing import Dict, List, Any, Optional
from uuid import UUID
from pydantic import BaseModel
from app.schemas.transaction import TransactionResponse

class JobSummaryResponse(BaseModel):
    id: UUID
    job_id: UUID
    total_spend_inr: float
    total_spend_usd: float
    top_merchants: List[Dict[str, Any]]
    anomaly_count: int
    narrative: str
    risk_level: str

    model_config = {
        "from_attributes": True
    }

class CategoryBreakdownItem(BaseModel):
    total_amount: float
    transaction_count: int

class JobResultsResponse(BaseModel):
    job_id: UUID
    status: str
    cleaned_transactions: List[TransactionResponse]
    anomalies: List[TransactionResponse]
    category_breakdown: Dict[str, CategoryBreakdownItem]
    summary: Optional[JobSummaryResponse] = None
    total_cleaned: Optional[int] = None
    total_anomalies: Optional[int] = None

    model_config = {
        "from_attributes": True
    }
