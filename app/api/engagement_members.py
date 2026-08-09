# app/api/engagement_members.py

"""
Engagement membership endpoints.

Thin by design: every permission decision, every audit write, and every
validity check lives in app/services/engagement_member_service.py. This
module resolves the tenant from the JWT, reads the request context, and
shapes the response.

Note the RBAC layering. require_staff_or_above is the floor -- it only keeps
client portal users out. The real rule (engagement administrator, or manager
or firm owner) is per-engagement, needs the database, and is therefore
enforced in the service, not in a role dependency.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.engagement_member import (
    EngagementMemberCreate,
    EngagementMemberOut,
    EngagementMemberUpdate,
)
from app.schemas.pagination import PaginatedResponse
import app.services.engagement_member_service as member_service

router = APIRouter(prefix="/engagements", tags=["engagement-members"])


def _request_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else None
    )
    return ip, request.headers.get("user-agent")


def _to_out(member, db: Session) -> EngagementMemberOut:
    out = EngagementMemberOut.model_validate(member)
    user = db.get(User, member.user_id)
    if user:
        out.user_name = user.full_name
        out.user_email = user.email
        out.user_role = str(user.role.value if hasattr(user.role, "value") else user.role)
    return out


# ---------------------------------------------------------
# LIST MEMBERS
# This is the source for the task assignment dropdown on a client task.
# ---------------------------------------------------------
@router.get("/{engagement_id}/members", response_model=PaginatedResponse[EngagementMemberOut])
def list_engagement_members(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    query = member_service.list_members(
        db=db, firm_id=current_firm.id, engagement_id=engagement_id
    )
    total = query.count()
    members = query.offset(offset).limit(limit).all()
    return PaginatedResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_out(m, db) for m in members],
    )


# ---------------------------------------------------------
# ADD MEMBER
# ---------------------------------------------------------
@router.post(
    "/{engagement_id}/members",
    response_model=EngagementMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_engagement_member(
    engagement_id: UUID,
    payload: EngagementMemberCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    ip, user_agent = _request_context(request)
    member = member_service.add_member(
        db=db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        payload=payload,
        current_user=current_user,
        ip_address=ip,
        user_agent=user_agent,
    )
    return _to_out(member, db)


# ---------------------------------------------------------
# PROMOTE / DEMOTE
# ---------------------------------------------------------
@router.patch("/{engagement_id}/members/{member_id}", response_model=EngagementMemberOut)
def update_engagement_member(
    engagement_id: UUID,
    member_id: UUID,
    payload: EngagementMemberUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    ip, user_agent = _request_context(request)
    member = member_service.update_member(
        db=db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        member_id=member_id,
        payload=payload,
        current_user=current_user,
        ip_address=ip,
        user_agent=user_agent,
    )
    return _to_out(member, db)


# ---------------------------------------------------------
# REMOVE MEMBER
# ---------------------------------------------------------
@router.delete(
    "/{engagement_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_engagement_member(
    engagement_id: UUID,
    member_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    ip, user_agent = _request_context(request)
    member_service.remove_member(
        db=db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        member_id=member_id,
        current_user=current_user,
        ip_address=ip,
        user_agent=user_agent,
    )
