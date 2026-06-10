from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
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

@router.post("/register", response_model=UserRead)
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
        hashed_password=hash_password(user.password),
        role="viewer"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=Token)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.username == request.username)
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login/swagger", response_model=Token)
def login_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Form-data login for Swagger UI authorization."""
    user = (
        db.query(User)
        .filter(User.username == form_data.username)
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}
