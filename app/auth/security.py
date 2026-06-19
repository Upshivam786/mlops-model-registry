"""
app/auth/security.py

JWT access + refresh token generation and verification.

Access token  : 60 minutes  — used for API calls
Refresh token : 7 days      — used to get a new access token without re-login
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

SECRET_KEY               = os.getenv("SECRET_KEY", "CHANGE_ME_SUPER_SECRET")
ALGORITHM                = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES  = 60
REFRESH_TOKEN_EXPIRE_DAYS    = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({
        "exp":  datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({
        "exp":  datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify any token (access or refresh).
    Returns payload dict on success, None on failure.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
