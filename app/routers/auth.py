"""
app/routers/auth.py

Authentication endpoints.

POST /auth/register        → register new user (role=viewer)
POST /auth/login           → JSON login, returns access + refresh token
POST /auth/login/swagger   → form-data login for Swagger UI
POST /auth/refresh         → exchange refresh token for new access token
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import User
from app.schemas import UserCreate, UserRead, LoginRequest, Token
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username exists")

    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        role="viewer",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=Token)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    payload = {"sub": user.username, "role": user.role}
    return {
        "access_token":  create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type":    "bearer",
    }


@router.post("/login/swagger", response_model=Token)
def login_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Form-data login for Swagger UI Authorize button."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    payload = {"sub": user.username, "role": user.role}
    return {
        "access_token":  create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
        "token_type":    "bearer",
    }


@router.post("/refresh", response_model=Token)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh token for a new access token + refresh token.
    The old refresh token is invalidated implicitly (stateless rotation).

    Usage:
      POST /auth/refresh?refresh_token=<your_refresh_token>
    """
    payload = decode_token(refresh_token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    # Issue fresh tokens with current role (picks up any role changes)
    new_payload = {"sub": user.username, "role": user.role}
    return {
        "access_token":  create_access_token(new_payload),
        "refresh_token": create_refresh_token(new_payload),
        "token_type":    "bearer",
    }
