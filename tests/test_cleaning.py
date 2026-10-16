import os
import tempfile
import pytest
from datetime import date
from app.services.cleaning import parse_date, parse_amount, clean_csv

def test_parse_date():
    assert parse_date("04-09-2024") == date(2024, 9, 4)
    assert parse_date("2024/02/05") == date(2024, 2, 5)
    assert parse_date("2024-07-15") == date(2024, 7, 15)
    assert parse_date("  17-02-2024  ") == date(2024, 2, 17)
    assert parse_date("invalid-date") is None
    assert parse_date("") is None

def test_parse_amount():
    assert parse_amount("10882.55") == 10882.55
    assert parse_amount("10,882.55") == 10882.55
    assert parse_amount("$11,325.79") == 11325.79
    assert parse_amount("  ₹12,092.64 ") == 12092.64
    assert parse_amount("-45.50") == -45.50
    assert parse_amount("(45.50)") == -45.50
    assert parse_amount("invalid-amount") is None
    assert parse_amount("") is None

def test_clean_csv():
    csv_content = """txn_id,date,merchant,amount,currency,status,category,account_id,notes
TXN1000,04-09-2024,Flipkart,100.50,INR,SUCCESS,Shopping,ACC001,notes1
TXN1000,04-09-2024,Flipkart,100.50,INR,SUCCESS,Shopping,ACC001,notes1
TXN1001,2024/02/05,Swiggy,$200.00,inr,success,,ACC002,notes2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content)
        temp_path = temp_file.name

    try:
        cleaned_rows, raw_count, cleaned_count = clean_csv(temp_path)
        
        # Verify deduplication
        assert raw_count == 3
        assert cleaned_count == 2
        
        # Verify row 1
        row1 = cleaned_rows[0]
        assert row1["txn_id"] == "TXN1000"
        assert row1["date"] == date(2024, 9, 4)
        assert row1["merchant"] == "Flipkart"
        assert row1["amount"] == 100.50
        assert row1["currency"] == "INR"
        assert row1["status"] == "SUCCESS"
        assert row1["category"] == "Shopping"
        
        # Verify row 2 (with missing category and dollar amount)
        row2 = cleaned_rows[1]
        assert row2["txn_id"] == "TXN1001"
        assert row2["date"] == date(2024, 2, 5)
        assert row2["amount"] == 200.00
        assert row2["currency"] == "INR"
        assert row2["status"] == "SUCCESS"
        assert row2["category"] == "Uncategorised"  # Default fallback
        
    finally:
        os.remove(temp_path)

def test_clean_csv_deduplication_different_notes_and_whitespace_headers():
    csv_content = """ txn_id , date , merchant , amount , currency , status , category , account_id , notes 
TXN999,01-01-2024,Amazon,"1,000.00",INR,SUCCESS,Shopping,ACC01,First note
TXN999,01-01-2024,Amazon,"1,000.00",INR,SUCCESS,Shopping,ACC01,Duplicate note?
TXN888,02-01-2024,Zomato,25.00,USD,SUCCESS,Food,ACC01,Normal txn
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as temp_file:
        temp_file.write(csv_content)
        temp_path = temp_file.name

    try:
        cleaned_rows, raw_count, cleaned_count = clean_csv(temp_path)
        assert raw_count == 3
        assert cleaned_count == 2
        assert cleaned_rows[0]["txn_id"] == "TXN999"
        assert cleaned_rows[0]["amount"] == 1000.00
        assert cleaned_rows[1]["txn_id"] == "TXN888"
    finally:
        os.remove(temp_path)
