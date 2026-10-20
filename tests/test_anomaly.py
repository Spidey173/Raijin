from app.services.anomaly import detect_anomalies

def test_anomaly_detection_rules():
    transactions = [
        # Account 1 - Median is 100
        {"account_id": "ACC01", "amount": 100.0, "currency": "INR", "merchant": "Amazon"},
        {"account_id": "ACC01", "amount": 100.0, "currency": "INR", "merchant": "Amazon"},
        {"account_id": "ACC01", "amount": 100.0, "currency": "INR", "merchant": "Amazon"},
        # 301 is > 3 * 100 -> Anomaly (Rule 1)
        {"account_id": "ACC01", "amount": 301.0, "currency": "INR", "merchant": "Amazon"},
        
        # Account 2 - Median is 50
        {"account_id": "ACC02", "amount": 50.0, "currency": "INR", "merchant": "Flipkart"},
        {"account_id": "ACC02", "amount": 50.0, "currency": "INR", "merchant": "Flipkart"},
        # Rule 2: USD for Swiggy -> Anomaly
        {"account_id": "ACC02", "amount": 20.0, "currency": "USD", "merchant": "Swiggy"},
        # Rule 2: USD for IRCTC -> Anomaly
        {"account_id": "ACC02", "amount": 10.0, "currency": "USD", "merchant": "IRCTC"},
        # USD for Amazon -> Safe
        {"account_id": "ACC02", "amount": 30.0, "currency": "USD", "merchant": "Amazon"},
    ]

    results = detect_anomalies(transactions)
    
    # Check Account 1 Anomaly
    assert results[0]["is_anomaly"] is False
    assert results[3]["is_anomaly"] is True
    assert "exceeds 3x median" in results[3]["anomaly_reason"]

    # Check Account 2 Anomalies
    assert results[4]["is_anomaly"] is False
    
    # Swiggy Anomaly
    assert results[6]["is_anomaly"] is True
    assert "Transaction in USD for domestic merchant" in results[6]["anomaly_reason"]
    
    # IRCTC Anomaly
    assert results[7]["is_anomaly"] is True
    assert "Transaction in USD for domestic merchant" in results[7]["anomaly_reason"]
    
    # Amazon USD Safe
    assert results[8]["is_anomaly"] is False

def test_anomaly_detection_zomato_usd_and_multi_currency():
    transactions = [
        # Account with both USD and INR transactions
        {"account_id": "ACC03", "amount": 10.0, "currency": "USD", "merchant": "AWS"},
        {"account_id": "ACC03", "amount": 15.0, "currency": "USD", "merchant": "GitHub"},
        {"account_id": "ACC03", "amount": 20.0, "currency": "USD", "merchant": "DigitalOcean"},
        # INR transaction in same account - Should NOT be compared to the 15 USD median!
        {"account_id": "ACC03", "amount": 1500.0, "currency": "INR", "merchant": "Amazon India"},
        {"account_id": "ACC03", "amount": 1500.0, "currency": "INR", "merchant": "Amazon India"},
        # Zomato domestic merchant charged in USD
        {"account_id": "ACC03", "amount": 250.0, "currency": "USD", "merchant": "Zomato"},
    ]

    results = detect_anomalies(transactions)
    
    # Normal USD transactions
    assert results[0]["is_anomaly"] is False
    assert results[1]["is_anomaly"] is False
    assert results[2]["is_anomaly"] is False
    
    # INR transaction is NOT an anomaly because it's evaluated against INR median (1500 INR)
    assert results[3]["is_anomaly"] is False
    assert results[4]["is_anomaly"] is False
    
    # Zomato USD is flagged both for domestic USD and exceeding 3x USD median
    zomato_txn = results[5]
    assert zomato_txn["is_anomaly"] is True
    assert "domestic merchant 'Zomato'" in zomato_txn["anomaly_reason"]
