# app/api/document_favorites.py
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.services import document_favorites_service

router = APIRouter(prefix="/document-favorites", tags=["document-favorites"])


class FavoriteCreate(BaseModel):
    item_type: str
    item_id: uuid.UUID


@router.post("/", status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Favorite a document or folder. Private to the requesting user."""
    fav = document_favorites_service.add_favorite(
        db,
        firm_id=current_firm.id,
        user_id=current_user.id,
        item_type=payload.item_type,
        item_id=payload.item_id,
    )
    return {"id": str(fav.id), "item_type": fav.item_type, "item_id": str(fav.item_id)}


@router.delete("/{item_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    item_type: str,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Remove a favorite. No error if not currently favorited (idempotent)."""
    document_favorites_service.remove_favorite(
        db,
        firm_id=current_firm.id,
        user_id=current_user.id,
        item_type=item_type,
        item_id=item_id,
    )


@router.get("/")
def list_favorites(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Return the current user's own favorites. Scoped by user_id from JWT."""
    return document_favorites_service.list_favorites(
        db,
        firm_id=current_firm.id,
        user_id=current_user.id,
    )
