from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import create_access_token, get_current_user_id
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

class TokenRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="The user or tenant identifier requesting the token.")
    password: Optional[str] = Field(default=None, description="Optional password for credentials check.")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    expires_in_seconds: int

@router.post("/token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def issue_token(req: TokenRequest):
    """
    Issues a cryptographically signed HS256 JWT access token for the given user/tenant.
    """
    user_id = req.user_id.strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id cannot be blank."
        )

    token = create_access_token(user_id=user_id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user_id,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.get("/me", status_code=status.HTTP_200_OK)
def get_authenticated_user(current_user: str = Depends(get_current_user_id)):
    """
    Returns the currently authenticated user/tenant identity decoded from the cryptographic token.
    """
    return {
        "authenticated": True,
        "user_id": current_user
    }
