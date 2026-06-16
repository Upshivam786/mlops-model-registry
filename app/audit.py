"""
app/audit.py

Single function that writes one row to audit_logs.
Call this inside any route that mutates data.

Usage:
    from app.audit import write_audit_log

    write_audit_log(
        db           = db,
        user         = current_user,
        action       = "CREATE",
        resource_type= "model",
        resource_id  = db_model.id,
        new_value    = {"name": db_model.name},
    )

Actions  : CREATE | UPDATE | DELETE | PROMOTE
Resources: model  | model_version | artifact
"""

import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import AuditLog, User


def write_audit_log(
    db: Session,
    user: User,
    action: str,
    resource_type: str,
    resource_id: int,
    old_value: dict = None,
    new_value: dict = None,
) -> None:
    """
    Write one immutable audit log entry.
    Never raises — if logging fails, it logs the error but does NOT
    break the actual API request. Audit failures must never block users.
    """
    try:
        log = AuditLog(
            user_id       = user.id,
            username      = user.username,
            action        = action,
            resource_type = resource_type,
            resource_id   = resource_id,
            old_value     = json.dumps(old_value)  if old_value else None,
            new_value     = json.dumps(new_value)  if new_value else None,
            timestamp     = datetime.utcnow(),
        )
        db.add(log)
        db.flush()   # write inside the current transaction, commit happens in the route
    except Exception as e:
        # Never let audit logging crash the real request
        import logging
        logging.getLogger(__name__).error("Audit log write failed: %s", e)
