import csv
import logging
import re
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger("raijin")

DATE_FORMATS = [
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y.%m.%d",
    "%d.%m.%Y"
]

def parse_date(date_str: str) -> Optional[date]:
    if not date_str or not str(date_str).strip():
        return None
    
    clean_date_str = str(date_str).strip()
    
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(clean_date_str, fmt).date()
        except ValueError:
            continue
            
    logger.warning(f"Could not parse date string: {date_str}")
    return None

def parse_amount(amount_str: Any) -> Optional[float]:
    if amount_str is None:
        return None
    if isinstance(amount_str, (int, float)):
        return round(float(amount_str), 2)
        
    s = str(amount_str).strip()
    if not s:
        return None
        
    # Check for accounting style negative: (100.00) -> -100.00
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()

    # Remove commas and non-numeric symbols except dot
    clean_str = re.sub(r"[^\d\.]", "", s)
    if not clean_str:
        return None
        
    try:
        val = float(clean_str)
        if is_negative:
            val = -val
        return round(val, 2)
    except ValueError:
        logger.warning(f"Could not parse amount string: {amount_str}")
        return None

def clean_csv(file_path: str) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Parses, cleans, and intelligently deduplicates rows from a transaction CSV file.
    
    Deduplication rules:
    - If txn_id is present: deduplicate strictly on txn_id.
    - If txn_id is missing: deduplicate on (date, merchant, amount, currency, status, account_id).
    
    Returns:
        tuple: (list of cleaned row dictionaries, raw row count, cleaned row count)
    """
    raw_count = 0
    cleaned_rows: List[Dict[str, Any]] = []
    seen_txn_ids = set()
    seen_fallback_signatures = set()

    try:
        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                # Strip keys and values
                row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k is not None}
                
                # Ignore completely empty rows
                if not any(row.values()):
                    continue
                    
                raw_count += 1

                # Normalize fields
                raw_txn_id = row.get("txn_id", "").strip()
                txn_id = raw_txn_id if raw_txn_id else None
                
                date_raw = row.get("date", "")
                parsed_date = parse_date(date_raw)
                
                raw_merchant = row.get("merchant", "").strip()
                merchant = raw_merchant if raw_merchant else None
                
                amount_raw = row.get("amount", "")
                parsed_amount = parse_amount(amount_raw)
                
                currency_raw = row.get("currency", "").strip()
                currency = currency_raw.upper() if currency_raw else "INR"
                
                status_raw = row.get("status", "").strip()
                status = status_raw.upper() if status_raw else "SUCCESS"
                
                category_raw = row.get("category", "").strip()
                category = category_raw if category_raw else "Uncategorised"
                
                raw_account = row.get("account_id", "").strip()
                account_id = raw_account if raw_account else None
                
                raw_notes = row.get("notes", "").strip()
                notes = raw_notes if raw_notes else None

                # Deduplication logic
                if txn_id:
                    if txn_id in seen_txn_ids:
                        continue
                    seen_txn_ids.add(txn_id)
                else:
                    fallback_sig = (
                        parsed_date.isoformat() if parsed_date else None,
                        merchant.upper() if merchant else None,
                        parsed_amount,
                        currency,
                        status,
                        account_id
                    )
                    if fallback_sig in seen_fallback_signatures:
                        continue
                    seen_fallback_signatures.add(fallback_sig)

                cleaned_rows.append({
                    "txn_id": txn_id,
                    "date": parsed_date,
                    "merchant": merchant,
                    "amount": parsed_amount,
                    "currency": currency,
                    "status": status,
                    "category": category,
                    "account_id": account_id,
                    "notes": notes
                })

    except Exception as e:
        logger.error(f"Error reading CSV file at {file_path}: {e}", exc_info=True)
        raise e

    cleaned_count = len(cleaned_rows)
    logger.info(f"CSV Cleaning completed. Raw rows: {raw_count}, Cleaned rows: {cleaned_count}")
    return cleaned_rows, raw_count, cleaned_count
