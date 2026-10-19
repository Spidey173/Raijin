from typing import Dict, List, Any

def detect_anomalies(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for txn in transactions:
        amount = txn.get("amount")
        if amount is not None and amount < 0:
            txn["is_anomaly"] = True
            txn["anomaly_reason"] = "Negative transaction amount"
        else:
            txn["is_anomaly"] = False
            txn["anomaly_reason"] = None
    return transactions
