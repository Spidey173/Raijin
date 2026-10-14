from typing import Dict, List, Optional
from pydantic import BaseModel

class SummaryStats(BaseModel):
    total_transactions: int
    total_amount: float
    currency: str

class CategoryBreakdownItem(BaseModel):
    category: str
    count: int
    total_amount: float
    percentage: float

class JobResultsResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    total_rows: int
    category_breakdown: List[CategoryBreakdownItem]
    account_summaries: Dict[str, SummaryStats]
