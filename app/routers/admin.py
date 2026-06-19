"""
app/routers/admin.py

Phase 4C — Role Management API

Admin-only endpoints for user management.
Eliminates the need for direct psql access to change roles.

GET    /admin/users              → list all users
PUT    /admin/users/{id}/role    → promote or demote a user
DELETE /admin/users/{id}         → deactivate a user (soft delete)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.dependencies import get_db
from app.auth.dependencies import require_admin
from app.models import User
from app.schemas import UserRead
from app.audit import write_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ROLES = {"viewer", "ml_engineer", "admin"}


class RoleUpdate(BaseModel):
    role: str


class UserList(BaseModel):
    users: List[UserRead]
    total: int


@router.get("/users", response_model=UserList)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all registered users with their roles. Admin only."""
    users = db.query(User).order_by(User.created_at.asc()).all()
    return UserList(users=users, total=len(users))


@router.put("/users/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Promote or demote a user role.
    Valid roles: viewer | ml_engineer | admin
    Admin only.
    """
    if role_in.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role_in.role}'. Valid roles: {sorted(VALID_ROLES)}",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    old_role = user.role
    user.role = role_in.role

    write_audit_log(
        db=db, user=current_user,
        action="UPDATE", resource_type="user", resource_id=user.id,
        old_value={"role": old_role},
        new_value={"role": role_in.role},
    )

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", response_model=UserRead)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Deactivate a user account (soft delete — sets is_active=False).
    The user can no longer log in but their audit history is preserved.
    Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    user.is_active = False

    write_audit_log(
        db=db, user=current_user,
        action="DELETE", resource_type="user", resource_id=user.id,
        old_value={"username": user.username, "is_active": True},
        new_value={"is_active": False},
    )

    db.commit()
    db.refresh(user)
    return user
