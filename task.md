# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# Section 3 - The task

TASK 1 OF 3: Audit log API endpoint -- new file app/api/audit_log.py

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before phase 4F audit log"

VERIFY BEFORE ACT:
ls /home/corby/jamm-os/app/api/ | grep audit
Confirm no audit_log.py exists yet.

---

Change 1: Create app/api/audit_log.py

Create new file at /home/corby/jamm-os/app/api/audit_log.py with this content:

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

---

Change 2: Register the router in app/main.py

VERIFY BEFORE ACT:
grep -n "audit\|from app.api" /home/corby/jamm-os/app/main.py | head -20
Paste output before touching anything.

Find the block where other routers are imported and registered.
Add the audit log router following the same pattern as the others.

Import:
from app.api.audit_log import router as audit_log_router

Register (find the line with app.include_router for another router and
add this immediately after it):
app.include_router(audit_log_router, prefix="/api/v1")

VERIFY AFTER ACT:
grep -n "audit_log" /home/corby/jamm-os/app/main.py
Confirm the import and include_router both appear.
python3 -c "from app.api.audit_log import router; print('OK')"
Must pass before stopping.