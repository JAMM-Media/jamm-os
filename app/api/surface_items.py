# app/api/surface_items.py

"""
The two curated surfaces and the owner actions on them.

Owner and manager only: staff never see either surface. Every route is
firm-scoped, and absent-or-another-firm's is a 404 in both cases, so a probe
cannot tell the difference.

Thin, as routers here are. Every decision lives in surface_item_service; these
functions resolve the tenant, hand off, and shape the response.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.surface_item import (
    BriefingResponse,
    ObservatoryResponse,
    PromoteNextResponse,
    SurfaceItemDismissRequest,
    SurfaceItemOut,
)
from app.services import surface_item_service

router = APIRouter(tags=["surfaces"])


@router.get("/briefing", response_model=BriefingResponse)
def get_briefing(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return surface_item_service.get_briefing(db, current_firm.id, actor_id=current_user.id)


@router.get("/observatory", response_model=ObservatoryResponse)
def get_observatory(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    return surface_item_service.get_observatory(db, current_firm.id)


@router.post("/briefing/promote-next", response_model=PromoteNextResponse)
def promote_next(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    item = surface_item_service.promote_next_briefing_item(db, current_firm.id)
    if item is None:
        return PromoteNextResponse(
            promoted=False,
            detail="Nothing else is waiting. The list is current.",
        )
    return PromoteNextResponse(
        promoted=True,
        detail="Promoted the next item.",
        item=SurfaceItemOut.model_validate(item),
    )


@router.post("/surface-items/{item_id}/dismiss", response_model=SurfaceItemOut)
def dismiss_item(
    item_id: UUID,
    payload: SurfaceItemDismissRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    item = surface_item_service.get_item_for_firm(db, item_id, current_firm.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return surface_item_service.dismiss_item(
        db, item, payload.reason, actor_id=current_user.id
    )


@router.post("/surface-items/{item_id}/implement", response_model=SurfaceItemOut)
def implement_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    item = surface_item_service.get_item_for_firm(db, item_id, current_firm.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return surface_item_service.implement_item(db, item, actor_id=current_user.id)
