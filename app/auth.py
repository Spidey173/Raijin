import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from app.models.job import Job

logger = logging.getLogger("raijin")

def get_current_user_id(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
    authorization: Optional[str] = Header(default=None)
) -> str:
    """
    Extracts the authenticated user / tenant identity.
    Precedence:
      1. X-User-ID header
      2. Bearer token subject from Authorization header
      3. Defaults to 'default-user' for unauthenticated/testing flows.
    """
    if x_user_id and x_user_id.strip():
        return x_user_id.strip()
        
    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
            
    return "default-user"

def verify_job_ownership(job: Job, user_id: str) -> None:
    """
    Enforces tenant/user ownership on job operations.
    If the job has an owner_id and the requesting user does not match,
    a 403 Forbidden exception is raised.
    """
    if job.owner_id and job.owner_id != user_id:
        logger.warning(f"Unauthorized access attempt: user '{user_id}' tried to access job '{job.id}' owned by '{job.owner_id}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have ownership of this job."
        )

