import statistics
from collections import defaultdict
from typing import Dict, List, Any, Tuple

# Comprehensive list of domestic Indian services/merchants where USD charges are anomalies
DOMESTIC_MERCHANTS_USD_RESTRICTED = {
    "SWIGGY",
    "ZOMATO",
    "OLA",
    "IRCTC",
    "FLIPKART",
    "BLINKIT",
    "ZEPTO",
    "BIGBASKET",
    "JIOMART",
    "JIO RECHARGE",
    "CRED",
    "PHONEPE",
    "PAYTM"
}

def detect_anomalies(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Applies multi-currency statistical and rule-based anomaly detection:
      Rule 1: Amount exceeds 3x the median for that specific account and currency.
      Rule 2: Foreign currency (USD) transaction for purely domestic Indian merchants.
      
    Mutates transactions in-place and returns the updated list with:
      - 'is_anomaly': bool
      - 'anomaly_reason': str or None
    """
    # Group amounts strictly by (account_id, currency) to prevent multi-currency distortion
    account_currency_amounts: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    
    for txn in transactions:
        acc_id = txn.get("account_id")
        amount = txn.get("amount")
        currency = (txn.get("currency") or "INR").upper()
        
        if acc_id and amount is not None and amount > 0:
            account_currency_amounts[(acc_id, currency)].append(amount)

    # Compute median for each (account_id, currency) pair
    account_currency_medians: Dict[Tuple[str, str], float] = {}
    for key, amounts in account_currency_amounts.items():
        if amounts:
            account_currency_medians[key] = statistics.median(amounts)
        else:
            account_currency_medians[key] = 0.0

    # Evaluate rules for each transaction
    for txn in transactions:
        reasons = []
        acc_id = txn.get("account_id")
        amount = txn.get("amount")
        currency = (txn.get("currency") or "INR").upper()
        merchant = txn.get("merchant")

        # Rule 1: Amount > 3x median for (account_id, currency)
        if acc_id and amount is not None and amount > 0:
            key = (acc_id, currency)
            median = account_currency_medians.get(key, 0.0)
            if median > 0 and amount > 3 * median:
                reasons.append(
                    f"Amount ({amount} {currency}) exceeds 3x median account amount ({median:.2f} {currency})"
                )

        # Rule 2: USD currency for domestic merchants
        if currency == "USD" and merchant:
            merchant_clean = merchant.strip().upper()
            if merchant_clean in DOMESTIC_MERCHANTS_USD_RESTRICTED:
                reasons.append(f"Transaction in USD for domestic merchant '{merchant.strip()}'")

        if reasons:
            txn["is_anomaly"] = True
            txn["anomaly_reason"] = " | ".join(reasons)
        else:
            txn["is_anomaly"] = False
            txn["anomaly_reason"] = None

    return transactions
