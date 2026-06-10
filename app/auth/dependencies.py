from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from fastapi.security import OAuth2PasswordBearer

from jose import jwt
from jose import JWTError

from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import User

from app.auth.security import (
    SECRET_KEY,
    ALGORITHM
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token"
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin required"
        )

    return user


def require_ml_engineer(user=Depends(get_current_user)):
    if user.role not in ["admin", "ml_engineer"]:
        raise HTTPException(
            status_code=403,
            detail="ML Engineer required"
        )

    return user
