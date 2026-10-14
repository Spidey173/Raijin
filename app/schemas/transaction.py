import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

class TransactionResponse(BaseModel):
    id: UUID
    txn_id: Optional[str] = None
    date: Optional[datetime.date] = None
    merchant: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    account_id: Optional[str] = None
    is_anomaly: bool
    anomaly_reason: Optional[str] = None
    llm_category: Optional[str] = None
    llm_failed: bool

    model_config = {
        "from_attributes": True
    }
