# app/api/audit_log.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.models.audit_log import AuditLog
from app.models.firm import Firm
from app.models.user import User

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("/")
def list_audit_log(
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    action: Optional[str] = None,
    actor_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    if current_user.role not in (UserRole.firm_owner, UserRole.manager):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    query = select(AuditLog).where(AuditLog.firm_id == current_firm.id)

    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)

    query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    rows = db.execute(query).scalars().all()

    # Resolve actor names
    actor_ids = list({r.actor_id for r in rows if r.actor_id})
    actor_map: dict = {}
    if actor_ids:
        users = db.execute(
            select(User).where(User.id.in_(actor_ids))
        ).scalars().all()
        actor_map = {str(u.id): u.full_name for u in users}

    items = []
    for row in rows:
        items.append({
            "id": str(row.id),
            "action": row.action,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "actor_name": actor_map.get(str(row.actor_id)) if row.actor_id else "System",
            "actor_type": row.actor_type,
            "entity_type": row.entity_type,
            "entity_id": str(row.entity_id) if row.entity_id else None,
            "ip_address": row.ip_address,
            "metadata": row.extra_metadata,
            "created_at": row.created_at.isoformat(),
        })

    # Total count for pagination
    from sqlalchemy import func
    count_query = select(func.count()).select_from(AuditLog).where(
        AuditLog.firm_id == current_firm.id
    )
    if action:
        count_query = count_query.where(AuditLog.action.ilike(f"%{action}%"))
    if actor_id:
        count_query = count_query.where(AuditLog.actor_id == actor_id)
    if entity_type:
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if date_from:
        count_query = count_query.where(AuditLog.created_at >= date_from)
    if date_to:
        count_query = count_query.where(AuditLog.created_at <= date_to)

    total = db.execute(count_query).scalar() or 0

    return {"items": items, "total": total, "skip": skip, "limit": limit}
