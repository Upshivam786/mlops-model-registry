from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.dependencies import get_db

from app.models import User

from app.schemas import (
    UserCreate,
    UserRead,
    LoginRequest,
    Token
)

from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post(
    "/register",
    response_model=UserRead
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(User)
        .filter(User.username == user.username)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Username exists"
        )

    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(
            user.password
        ),
        role="viewer"
    )

    db.add(db_user)

    db.commit()

    db.refresh(db_user)

    return db_user


@router.post(
    "/login",
    response_model=Token
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    print("LOGIN 1")

    user = (
        db.query(User)
        .filter(
            User.username == request.username
        )
        .first()
    )

    print("LOGIN 2", user)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    result = verify_password(
        request.password,
        user.hashed_password
    )

    print("LOGIN 3", result)

    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token(
        {
            "sub": user.username,
            "role": user.role
        }
    )

    print("LOGIN 4", token[:20])

    response = {
        "access_token": token,
        "token_type": "bearer"
    }

    print("LOGIN 5")

    return response
