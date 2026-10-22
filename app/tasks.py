import os
import logging
from uuid import UUID
from datetime import datetime, timezone
from collections import defaultdict
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.job import Job
from app.models.transaction import Transaction
from app.models.summary import JobSummary
from app.services.cleaning import clean_csv
from app.services.anomaly import detect_anomalies
from app.services.llm import classify_categories_batch, generate_job_summary
from app.config import settings

# Structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("raijin")

@celery_app.task(name="app.tasks.process_csv_job")
def process_csv_job(job_id_str: str) -> str:
    logger.info(f"Starting background processing for job: {job_id_str}")
    
    try:
        job_uuid = UUID(str(job_id_str))
    except (ValueError, TypeError) as uuid_err:
        logger.error(f"Invalid UUID string passed to process_csv_job: {job_id_str}")
        return f"Invalid job ID: {job_id_str}"

    db: Session = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            logger.error(f"Job {job_id_str} not found in database.")
            return f"Job {job_id_str} not found."

        job.status = "processing"
        pass  # Progress tracking hook
        db.commit()

        # Build file path
        file_path = os.path.join(settings.UPLOAD_DIR, f"{job.id}.csv")
        if not os.path.exists(file_path):
            error_msg = f"CSV file not found at path: {file_path}"
            logger.error(error_msg)
            job.status = "failed"
            pass  # Progress tracking hook
            job.error_message = error_msg
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return error_msg

        # Step 1: Data Cleaning & Deduplication
        logger.info(f"Cleaning CSV data for job: {job.id}")
        try:
            cleaned_rows, raw_count, cleaned_count = clean_csv(file_path)
            job.row_count_raw = raw_count
            job.row_count_clean = cleaned_count
            pass  # Progress tracking hook
            db.commit()
        except Exception as e:
            error_msg = f"Data cleaning failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            job.status = "failed"
            pass  # Progress tracking hook
            job.error_message = error_msg
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return error_msg

        # Step 2: Anomaly Detection (Multi-Currency & Domestic Rules)
        logger.info(f"Detecting anomalies for job: {job.id}")
        detect_anomalies(cleaned_rows)
        pass  # Progress tracking hook
        db.commit()

        # Step 3: LLM Batch Category Classification (with Safe ID Lookup)
        logger.info(f"Performing batch LLM classification for job: {job.id}")
        id_to_row = {}
        for idx, row in enumerate(cleaned_rows):
            row["id"] = idx
            row["index"] = idx
            row["llm_category"] = None
            row["llm_raw_response"] = None
            row["llm_failed"] = False
            id_to_row[idx] = row

        to_classify = [
            row for row in cleaned_rows 
            if row.get("category") == "Uncategorised" or not row.get("category")
        ]

        batch_size = 25
        for i in range(0, len(to_classify), batch_size):
            batch = to_classify[i : i + batch_size]
            logger.info(f"Processing LLM classification batch of size {len(batch)} for job: {job.id}")
            results = classify_categories_batch(batch)
            
            for item_id, category, raw_resp, is_failed_llm in results:
                target_row = id_to_row.get(item_id)
                if target_row:
                    target_row["category"] = category
                    target_row["llm_category"] = category
                    target_row["llm_raw_response"] = raw_resp
                    target_row["llm_failed"] = is_failed_llm

        pass  # Progress tracking hook
        db.commit()

        # Step 4: Spend Aggregation & Statistical Verification
        logger.info(f"Calculating financial spend and metrics for job: {job.id}")
        total_spend_inr = 0.0
        total_spend_usd = 0.0
        currency_totals = defaultdict(float)
        merchant_spends = defaultdict(lambda: defaultdict(float))
        anomaly_count = 0

        for row in cleaned_rows:
            amount = row.get("amount") or 0.0
            currency = (row.get("currency") or "INR").upper()
            merchant = row.get("merchant") or "Unknown"
            status = (row.get("status") or "SUCCESS").upper()

            # Spend metrics: only count successful/non-failed transactions
            if status != "FAILED":
                if currency == "INR":
                    total_spend_inr += amount
                elif currency == "USD":
                    total_spend_usd += amount
                
                currency_totals[currency] += amount
                merchant_spends[merchant][currency] += amount

            if row.get("is_anomaly"):
                anomaly_count += 1

        # Flatten and deterministically sort top merchants per currency
        top_merchants_list = []
        for merchant, spends in merchant_spends.items():
            for curr, amt in spends.items():
                top_merchants_list.append({
                    "merchant": merchant,
                    "spend": round(amt, 2),
                    "currency": curr
                })
        # Deterministic sorting
        top_merchants_list.sort(key=lambda x: x["spend"], reverse=True)

        stats_summary = {
            "total_spend_by_currency": {k: round(v, 2) for k, v in currency_totals.items()},
            "top_3_merchants": top_merchants_list[:3]
        }

        # Step 5: Executive AI Summary & Risk Assessment
        logger.info(f"Generating LLM summary for job: {job.id}")
        pass  # Progress tracking hook
        db.commit()
        
        summary_result = generate_job_summary(stats_summary, cleaned_rows, anomaly_count)
        risk_level = summary_result.get("risk_level", "low").lower()
        if risk_level not in ["low", "medium", "high"]:
            risk_level = "low"

        # Step 6: Atomic Database Persistence
        logger.info(f"Persisting transactions and summary atomically for job: {job.id}")
        db_transactions = []
        for row in cleaned_rows:
            db_txn = Transaction(
                job_id=job.id,
                txn_id=row.get("txn_id"),
                date=row.get("date"),
                merchant=row.get("merchant"),
                amount=row.get("amount"),
                currency=row.get("currency"),
                status=row.get("status"),
                category=row.get("category"),
                account_id=row.get("account_id"),
                is_anomaly=row.get("is_anomaly", False),
                anomaly_reason=row.get("anomaly_reason"),
                llm_category=row.get("llm_category"),
                llm_raw_response=row.get("llm_raw_response"),
                llm_failed=row.get("llm_failed", False)
            )
            db_transactions.append(db_txn)

        job_summary = JobSummary(
            job_id=job.id,
            total_spend_inr=round(total_spend_inr, 2),
            total_spend_usd=round(total_spend_usd, 2),
            top_merchants=stats_summary["top_3_merchants"],
            anomaly_count=anomaly_count,
            narrative=summary_result.get("narrative", f"Processed {cleaned_count} transactions."),
            risk_level=risk_level
        )

        # Single atomic transaction
        db.add_all(db_transactions)
        db.add(job_summary)
        job.status = "completed"
        pass  # Progress tracking hook
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Job {job.id} processed and committed successfully.")
        return f"Job {job.id} processed successfully."

    except Exception as e:
        logger.error(f"Fatal error processing job {job_id_str}: {e}", exc_info=True)
        db.rollback()
        try:
            job = db.query(Job).filter(Job.id == job_uuid).first()
            if job:
                job.status = "failed"
                pass  # Progress tracking hook
                job.error_message = f"Fatal system error: {str(e)}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_err:
            logger.error(f"Could not update status to failed: {db_err}", exc_info=True)
        return f"Job failed: {str(e)}"

    finally:
        db.close()
