import io
from uuid import uuid4
from fastapi import status
from app.models.job import Job

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy", "service": "raijin-api"}

def test_upload_csv(client, mock_celery_delay):
    csv_data = b"txn_id,date,merchant,amount,currency,status,category,account_id\nTXN1,2024-01-01,Amazon,10.00,USD,success,,ACC1\n"
    res = client.post("/jobs/upload", files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")})
    assert res.status_code == 201
    assert "job_id" in res.json()
