"""
app/routers/audit.py

Admin-only read endpoint for the audit log.

GET /audit-logs                          → paginated full log
GET /audit-logs?resource_type=model      → filter by resource
GET /audit-logs?action=PROMOTE           → filter by action
GET /audit-logs?username=shivam          → filter by user
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.dependencies import get_db
from app.auth.dependencies import require_admin
from app.models import AuditLog, User
from app.schemas import AuditLogRead, AuditLogList

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogList)
def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    resource_type: Optional[str] = None,   # model | model_version | artifact
    action: Optional[str] = None,          # CREATE | UPDATE | DELETE | PROMOTE
    username: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),   # admin only
):
    """
    Return audit log entries, newest first.
    Filter by resource_type, action, or username.
    """
    query = db.query(AuditLog)

    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if action:
        query = query.filter(AuditLog.action == action)
    if username:
        query = query.filter(AuditLog.username == username)

    total = query.count()
    logs = (
        query
        .order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return AuditLogList(logs=logs, total=total, page=page, size=size)
