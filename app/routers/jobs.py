import os
import shutil
from uuid import UUID
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models.job import Job
from app.models.transaction import Transaction
from app.models.summary import JobSummary
from app.auth import get_current_user_id, verify_job_ownership
from app.schemas.job import (
    JobStatusResponse,
    JobListResponse,
    JobListItem,
    PaginationMetadata,
    JobSummaryStats
)
from app.schemas.summary import JobResultsResponse, JobSummaryResponse, CategoryBreakdownItem
from app.schemas.transaction import TransactionResponse
from app.tasks import process_csv_job
from app.config import settings

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # 1. Validate file extension
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only CSV files are allowed."
        )

    # 2. Create Job record in pending state associated with the user
    job = Job(
        filename=filename,
        owner_id=user_id,
        status="pending",
        progress="0%"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{job.id}.csv")

    # 3. Stream upload in chunks with size limit enforcement
    total_bytes = 0
    chunk_size = 64 * 1024  # 64 KB
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB."
                    )
                f.write(chunk)
                
        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )
            
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.delete(job)
        db.commit()
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.delete(job)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save uploaded file: {str(e)}"
        )

    # 4. Dispatch background Celery job
    process_csv_job.delay(str(job.id))

    return {"job_id": job.id}

@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Ownership check
    verify_job_ownership(job, user_id)

    # Accurate progress reporting
    if job.status in ["completed", "failed"]:
        progress = "100%"
    elif getattr(job, "progress", None) and job.progress not in ["0%", None]:
        progress = job.progress
    elif job.status == "processing":
        progress = "50%"
    else:
        progress = "0%"

    summary_stats = None
    if job.status == "completed" and job.summary:
        summary_stats = JobSummaryStats(
            row_count_raw=job.row_count_raw,
            row_count_clean=job.row_count_clean,
            total_spend_inr=float(job.summary.total_spend_inr),
            total_spend_usd=float(job.summary.total_spend_usd),
            anomaly_count=job.summary.anomaly_count,
            risk_level=job.summary.risk_level
        )

    return JobStatusResponse(
        job_id=job.id,
        owner_id=job.owner_id,
        status=job.status,
        progress=progress,
        created_at=job.created_at,
        completed_at=job.completed_at,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        error_message=job.error_message,
        summary=summary_stats
    )

@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(
    job_id: UUID,
    page: Optional[int] = Query(default=None, ge=1, description="Optional page number for pagination"),
    size: Optional[int] = Query(default=None, ge=1, le=1000, description="Optional page size for pagination"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Ownership check
    verify_job_ownership(job, user_id)

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job.status}"
        )

    # 1. SQL Aggregation for Category Breakdown (constant memory footprint)
    cat_query = (
        db.query(
            Transaction.category,
            func.sum(Transaction.amount),
            func.count(Transaction.id)
        )
        .filter(Transaction.job_id == job_id)
        .group_by(Transaction.category)
        .all()
    )
    category_breakdown: Dict[str, CategoryBreakdownItem] = {}
    for cat_name, total_amt, txn_count in cat_query:
        key = cat_name or "Uncategorised"
        category_breakdown[key] = CategoryBreakdownItem(
            total_amount=round(float(total_amt or 0.0), 2),
            transaction_count=txn_count
        )

    # 2. SQL-Level Paginated Queries for Transactions
    txns_base = db.query(Transaction).filter(Transaction.job_id == job_id)
    total_cleaned = txns_base.count()

    anomalies_base = db.query(Transaction).filter(
        Transaction.job_id == job_id,
        Transaction.is_anomaly == True
    )
    total_anomalies = anomalies_base.count()

    if page is not None and size is not None:
        offset = (page - 1) * size
        txns_list = txns_base.order_by(Transaction.id).offset(offset).limit(size).all()
        anomalies_list = anomalies_base.order_by(Transaction.id).offset(offset).limit(size).all()
    else:
        txns_list = txns_base.order_by(Transaction.id).all()
        anomalies_list = anomalies_base.order_by(Transaction.id).all()

    cleaned_txns_response = [TransactionResponse.model_validate(t) for t in txns_list]
    anomalies_response = [TransactionResponse.model_validate(t) for t in anomalies_list]

    summary_resp = None
    if job.summary:
        summary_resp = JobSummaryResponse(
            id=job.summary.id,
            job_id=job.summary.job_id,
            total_spend_inr=float(job.summary.total_spend_inr),
            total_spend_usd=float(job.summary.total_spend_usd),
            top_merchants=job.summary.top_merchants,
            anomaly_count=job.summary.anomaly_count,
            narrative=job.summary.narrative,
            risk_level=job.summary.risk_level
        )

    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        cleaned_transactions=cleaned_txns_response,
        anomalies=anomalies_response,
        category_breakdown=category_breakdown,
        summary=summary_resp,
        total_cleaned=total_cleaned,
        total_anomalies=total_anomalies
    )

