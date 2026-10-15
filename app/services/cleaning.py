import csv
import logging
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger("raijin")

def parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None

def parse_amount(amount_str: Any) -> Optional[float]:
    if amount_str is None:
        return None
    try:
        return float(amount_str)
    except (ValueError, TypeError):
        return None

def clean_csv(file_path: str) -> Tuple[List[Dict[str, Any]], int, int]:
    valid_txns = []
    total_rows = 0
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            amt = parse_amount(row.get("amount"))
            dt = parse_date(row.get("date"))
            if amt is not None and dt is not None:
                valid_txns.append({
                    "txn_id": row.get("txn_id"),
                    "date": dt,
                    "merchant": row.get("merchant", "").strip(),
                    "amount": amt,
                    "currency": (row.get("currency") or "INR").strip().upper(),
                    "status": (row.get("status") or "SUCCESS").strip().upper(),
                    "category": row.get("category"),
                    "account_id": row.get("account_id", "").strip(),
                })
    return valid_txns, total_rows, len(valid_txns)
