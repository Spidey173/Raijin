import os
from uuid import UUID
from datetime import datetime, timezone
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.job import Job
from app.models.transaction import Transaction
from app.models.summary import JobSummary
from app.services.cleaning import clean_csv
from app.services.anomaly import detect_anomalies
from app.services.llm import classify_categories_batch, generate_job_summary
from app.config import settings

@celery_app.task(name="app.tasks.process_csv_job")
def process_csv_job(job_id_str: str) -> str:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == UUID(job_id_str)).first()
        if not job:
            return "Job not found"
        file_path = os.path.join(settings.UPLOAD_DIR, f"{job.id}.csv")
        cleaned, raw_cnt, clean_cnt = clean_csv(file_path)
        analyzed = detect_anomalies(cleaned)
        classified = classify_categories_batch(analyzed)
        job.status = "completed"
        db.commit()
        return "Success"
    finally:
        db.close()
