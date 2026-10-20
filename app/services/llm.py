import os
from typing import Dict, List, Any, Optional

ALLOWED_CATEGORIES = ["Food", "Shopping", "Travel", "Transport", "Utilities", "Cash Withdrawal", "Entertainment", "Other"]

def classify_categories_batch(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for txn in transactions:
        if not txn.get("category"):
            txn["category"] = "Other"
    return transactions

def generate_job_summary(transactions: List[Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "spending_overview": f"Processed {len(transactions)} transactions.",
        "risk_analysis": f"Identified {len(anomalies)} anomalies.",
        "merchant_insights": "Analysis completed."
    }
