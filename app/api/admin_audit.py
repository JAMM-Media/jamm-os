# app/api/admin_audit.py

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut
from app.schemas.pagination import PaginatedResponse
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner

router = APIRouter(prefix="/admin", tags=["admin"])


def _build_base_stmt(
    firm_id: uuid.UUID,
    action: Optional[str],
    entity_type: Optional[str],
    actor_id: Optional[uuid.UUID],
    start_date: Optional[date],
    end_date: Optional[date],
):
    stmt = select(AuditLog).where(AuditLog.firm_id == firm_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if start_date:
        start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        stmt = stmt.where(AuditLog.created_at >= start_dt)
    if end_date:
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)
        stmt = stmt.where(AuditLog.created_at <= end_dt)
    return stmt


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    base = _build_base_stmt(
        current_firm.id, action, entity_type, actor_id, start_date, end_date
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()

    items = db.execute(
        base.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    return PaginatedResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=list(items),
    )
