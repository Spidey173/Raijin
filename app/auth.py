import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import Header, HTTPException, status
from app.config import settings
from app.models.job import Job

logger = logging.getLogger("raijin")

def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a cryptographically signed JWT access token for a user or tenant.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id).strip(),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token

def decode_access_token(token: str) -> str:
    """
    Verifies the cryptographic signature and expiration of a JWT token,
    returning the authenticated user_id subject.
    """
    if not token or not str(token).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    try:
        payload = jwt.decode(
            token.strip(),
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if not user_id or not str(user_id).strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: user subject claim missing.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return str(user_id).strip()
    except jwt.ExpiredSignatureError:
        logger.warning("Rejected expired authentication token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as err:
        logger.warning(f"Rejected invalid authentication token: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: invalid token signature.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-ID"),
) -> str:
    """
    Cryptographically authenticates the caller and returns the tenant/user identity.
    
    Security rules:
      1. Cryptographically signed Bearer JWT: Signature and expiration are verified.
      2. Service-to-service API Key: Validated against settings.API_KEY.
         Only authenticated API Key clients may specify an X-User-ID tenant.
      3. Unauthenticated X-User-ID headers are strictly rejected to prevent identity spoofing.
      4. If unauthenticated:
         - If settings.ENABLE_ANONYMOUS_DEV_MODE is True: returns 'default-user'.
         - Otherwise: raises 401 Unauthorized.
    """
    # 1. Bearer JWT Authentication
    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            return decode_access_token(token)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Trusted API Key Authentication
    if x_api_key and x_api_key.strip():
        configured_key = settings.API_KEY.strip() if settings.API_KEY else ""
        if configured_key and x_api_key.strip() == configured_key:
            # Authenticated service-to-service caller
            if x_user_id and x_user_id.strip():
                return x_user_id.strip()
            return "api-service"
        else:
            logger.warning("Rejected invalid API Key.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    # 3. Prevent identity spoofing via unauthenticated X-User-ID
    if x_user_id and x_user_id.strip():
        logger.warning(f"Blocked unauthenticated identity spoofing attempt with X-User-ID: {x_user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted identity header: X-User-ID is only permitted when authenticated via a valid X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Anonymous dev mode fallback (only if explicitly enabled)
    if settings.ENABLE_ANONYMOUS_DEV_MODE:
        return "default-user"

    # Strict rejection for unauthenticated requests
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a cryptographically signed Bearer token or valid API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )

def verify_job_ownership(job: Job, user_id: str) -> None:
    """
    Enforces tenant/user ownership on job operations.
    If the job has an owner_id and the requesting user does not match,
    a 403 Forbidden exception is raised.
    """
    if job.owner_id and job.owner_id != user_id:
        logger.warning(
            f"Unauthorized tenant access attempt: user '{user_id}' tried to access job '{job.id}' owned by '{job.owner_id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have ownership of this job."
        )
