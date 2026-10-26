import os
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.job import Job
from app.tasks import process_csv_job
from app.config import settings

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type")
    job = Job(filename=file.filename, status="pending")
    db.add(job)
    db.commit()
    file_path = os.path.join(settings.UPLOAD_DIR, f"{job.id}.csv")
    with open(file_path, "wb") as f:
        f.write(await file.read())
    process_csv_job.delay(str(job.id))
    return {"job_id": str(job.id)}

@router.get("/{job_id}/status")
def get_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": str(job.id), "status": job.status}
