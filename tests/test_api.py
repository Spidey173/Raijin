import os
import io
import pytest
from uuid import uuid4
from fastapi import status
from app.models.job import Job
from app.models.transaction import Transaction
from app.models.summary import JobSummary

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "raijin-api"}

def test_upload_csv(client, mock_celery_delay):
    csv_data = b"txn_id,date,merchant,amount,currency,status,category,account_id\nTXN1,2024-01-01,Amazon,10.00,USD,success,,ACC1\n"
    response = client.post(
        "/jobs/upload",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")}
    )
    
    assert response.status_code == 201
    assert "job_id" in response.json()
    
    # Assert Celery task was enqueued
    assert len(mock_celery_delay) == 1
    assert mock_celery_delay[0][0][0] == response.json()["job_id"]

def test_upload_invalid_file_type(client):
    response = client.post(
        "/jobs/upload",
        files={"file": ("test.txt", io.BytesIO(b"some content"), "text/plain")}
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]

def test_get_job_status_pending(client, db):
    # Insert a job manually
    job = Job(id=uuid4(), filename="input.csv", status="pending")
    db.add(job)
    db.commit()

    response = client.get(f"/jobs/{job.id}/status")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "pending"
    assert res_json["progress"] == "0%"

def test_get_job_status_completed(client, db):
    job_id = uuid4()
    job = Job(id=job_id, filename="input.csv", status="completed", row_count_raw=10, row_count_clean=8)
    summary = JobSummary(
        job_id=job_id,
        total_spend_inr=1000.0,
        total_spend_usd=50.0,
        top_merchants=[],
        anomaly_count=1,
        narrative="Test Narrative",
        risk_level="low"
    )
    db.add(job)
    db.add(summary)
    db.commit()

    response = client.get(f"/jobs/{job_id}/status")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "completed"
    assert res_json["progress"] == "100%"
    assert res_json["summary"]["anomaly_count"] == 1
    assert res_json["summary"]["risk_level"] == "low"

def test_get_job_results_not_completed(client, db):
    job = Job(id=uuid4(), filename="input.csv", status="processing")
    db.add(job)
    db.commit()

    response = client.get(f"/jobs/{job.id}/results")
    assert response.status_code == 400
    assert "Job is not completed" in response.json()["detail"]

def test_get_job_results_completed(client, db):
    job_id = uuid4()
    job = Job(id=job_id, filename="input.csv", status="completed", row_count_raw=1, row_count_clean=1)
    
    # Add transaction
    txn = Transaction(
        job_id=job_id,
        txn_id="TXN1",
        date=None,
        merchant="Amazon",
        amount=100.0,
        currency="USD",
        status="SUCCESS",
        category="Shopping",
        account_id="ACC1",
        is_anomaly=True,
        anomaly_reason="High spend"
    )
    
    summary = JobSummary(
        job_id=job_id,
        total_spend_inr=0.0,
        total_spend_usd=100.0,
        top_merchants=[{"merchant": "Amazon", "spend": 100.0, "currency": "USD"}],
        anomaly_count=1,
        narrative="Amazon transaction flagged.",
        risk_level="high"
    )
    
    db.add(job)
    db.add(txn)
    db.add(summary)
    db.commit()

    response = client.get(f"/jobs/{job_id}/results")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "completed"
    assert len(res_json["cleaned_transactions"]) == 1
    assert len(res_json["anomalies"]) == 1
    assert "Shopping" in res_json["category_breakdown"]
    assert res_json["summary"]["narrative"] == "Amazon transaction flagged."

def test_list_jobs(client, db):
    # Insert multiple jobs
    db.add(Job(id=uuid4(), filename="file1.csv", status="completed"))
    db.add(Job(id=uuid4(), filename="file2.csv", status="failed"))
    db.add(Job(id=uuid4(), filename="file3.csv", status="completed"))
    db.commit()

    # List all
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json()["metadata"]["total"] == 3
    
    # Filter status=completed
    response = client.get("/jobs?status=completed")
    assert response.status_code == 200
    assert response.json()["metadata"]["total"] == 2

def test_upload_empty_csv(client):
    response = client.post(
        "/jobs/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    )
    assert response.status_code == 400
    assert "Uploaded file is empty" in response.json()["detail"]

def test_get_job_results_paginated(client, db):
    job_id = uuid4()
    job = Job(id=job_id, filename="input.csv", status="completed", row_count_raw=2, row_count_clean=2)
    txn1 = Transaction(job_id=job_id, txn_id="TXN1", amount=10.0, currency="USD", status="SUCCESS", category="Food")
    txn2 = Transaction(job_id=job_id, txn_id="TXN2", amount=20.0, currency="USD", status="SUCCESS", category="Travel")
    summary = JobSummary(
        job_id=job_id,
        total_spend_inr=0.0,
        total_spend_usd=30.0,
        top_merchants=[],
        anomaly_count=0,
        narrative="Test Narrative",
        risk_level="low"
    )
    db.add(job)
    db.add(txn1)
    db.add(txn2)
    db.add(summary)
    db.commit()

    # Request page 1 with size 1
    response = client.get(f"/jobs/{job_id}/results?page=1&size=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cleaned_transactions"]) == 1
    assert data["total_cleaned"] == 2

def test_retry_job_success(client, db, mock_celery_delay):
    job_id = uuid4()
    job = Job(id=job_id, filename="retry.csv", status="failed", error_message="Some error")
    db.add(job)
    db.commit()

    # Create dummy source file in upload dir
    from app.config import settings
    file_path = os.path.join(settings.UPLOAD_DIR, f"{job_id}.csv")
    with open(file_path, "w") as f:
        f.write("txn_id\nTXN1\n")

    try:
        response = client.post(f"/jobs/{job_id}/retry")
        assert response.status_code == 200
        assert "enqueued" in response.json()["message"]
        
        # Verify db status reset
        db.refresh(job)
        assert job.status == "pending"
        assert job.error_message is None
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def test_end_to_end_upload_and_process(client, db, mock_celery_delay):
    from unittest.mock import patch
    from sqlalchemy.orm import sessionmaker
    from app.tasks import process_csv_job
    
    # 1. Read transactions.csv
    with open("transactions.csv", "rb") as f:
        file_bytes = f.read()

    # 2. Upload file
    response = client.post(
        "/jobs/upload",
        files={"file": ("transactions.csv", io.BytesIO(file_bytes), "text/csv")}
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    # 3. Execute the Celery background task synchronously
    with patch("app.tasks.SessionLocal", lambda: db):
        task_result = process_csv_job(job_id)
        assert "processed successfully" in task_result

    # 4. Check status via API
    status_resp = client.get(f"/jobs/{job_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "completed"
    assert status_data["progress"] == "100%"
    assert status_data["row_count_raw"] == 95
    assert status_data["row_count_clean"] == 85
    assert status_data["summary"]["anomaly_count"] == 10

    # 5. Check results via API
    results_resp = client.get(f"/jobs/{job_id}/results")
    assert results_resp.status_code == 200
    results_data = results_resp.json()
    assert len(results_data["cleaned_transactions"]) == 85
    assert len(results_data["anomalies"]) == 10
    assert "Food" in results_data["category_breakdown"]
    assert results_data["summary"]["anomaly_count"] == 10

def test_job_ownership_enforcement(client, db):
    # Create job owned by alice
    alice_job_id = uuid4()
    job = Job(id=alice_job_id, filename="alice.csv", status="completed", owner_id="alice")
    summary = JobSummary(
        job_id=alice_job_id,
        total_spend_inr=100.0,
        total_spend_usd=0.0,
        top_merchants=[],
        anomaly_count=0,
        narrative="Alice narrative",
        risk_level="low"
    )
    db.add(job)
    db.add(summary)
    db.commit()

    # Bob tries to access Alice's job status -> 403 Forbidden
    response_bob = client.get(
        f"/jobs/{alice_job_id}/status",
        headers={"X-User-ID": "bob"}
    )
    assert response_bob.status_code == 403
    assert "Forbidden" in response_bob.json()["detail"]

    # Bob tries to access Alice's job results -> 403 Forbidden
    results_bob = client.get(
        f"/jobs/{alice_job_id}/results",
        headers={"X-User-ID": "bob"}
    )
    assert results_bob.status_code == 403
    assert "Forbidden" in results_bob.json()["detail"]

    # Alice accesses her own job status -> 200 OK
    response_alice = client.get(
        f"/jobs/{alice_job_id}/status",
        headers={"X-User-ID": "alice"}
    )
    assert response_alice.status_code == 200
    assert response_alice.json()["owner_id"] == "alice"

def test_list_jobs_ownership_isolation(client, db):
    job_alice = Job(id=uuid4(), filename="alice.csv", status="completed", owner_id="alice")
    job_bob = Job(id=uuid4(), filename="bob.csv", status="completed", owner_id="bob")
    db.add(job_alice)
    db.add(job_bob)
    db.commit()

    # Alice lists jobs -> sees only Alice's job
    res_alice = client.get("/jobs", headers={"X-User-ID": "alice"})
    assert res_alice.status_code == 200
    alice_job_ids = [j["id"] for j in res_alice.json()["jobs"]]
    assert str(job_alice.id) in alice_job_ids
    assert str(job_bob.id) not in alice_job_ids

    # Bob lists jobs -> sees only Bob's job
    res_bob = client.get("/jobs", headers={"X-User-ID": "bob"})
    assert res_bob.status_code == 200
    bob_job_ids = [j["id"] for j in res_bob.json()["jobs"]]
    assert str(job_bob.id) in bob_job_ids
    assert str(job_alice.id) not in bob_job_ids
