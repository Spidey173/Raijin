import statistics
from collections import defaultdict
from typing import Dict, List, Any, Tuple

def detect_anomalies(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    account_currency_amounts = defaultdict(list)
    for txn in transactions:
        acc_id = txn.get("account_id")
        amount = txn.get("amount")
        currency = (txn.get("currency") or "INR").upper()
        if acc_id and amount is not None and amount > 0:
            account_currency_amounts[(acc_id, currency)].append(amount)

    medians = {}
    for key, amounts in account_currency_amounts.items():
        medians[key] = statistics.median(amounts) if amounts else 0.0

    for txn in transactions:
        acc_id = txn.get("account_id")
        amount = txn.get("amount")
        currency = (txn.get("currency") or "INR").upper()
        med = medians.get((acc_id, currency), 0.0)
        if acc_id and amount and med > 0 and amount > 3.0 * med:
            txn["is_anomaly"] = True
            txn["anomaly_reason"] = f"Amount {amount} {currency} exceeds 3x median ({med:.2f})"
        else:
            txn["is_anomaly"] = False
            txn["anomaly_reason"] = None
    return transactions
