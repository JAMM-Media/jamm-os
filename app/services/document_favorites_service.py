# app/services/document_favorites_service.py
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_favorite import DocumentFavorite
from app.models.document_folder import DocumentFolder


def _validate_item_type(item_type: str) -> None:
    if item_type not in ("document", "folder"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="item_type must be 'document' or 'folder'",
        )


def _assert_item_exists(db: Session, firm_id: uuid.UUID, item_type: str, item_id: uuid.UUID) -> None:
    """Confirm the item exists, belongs to this firm, and is not soft-deleted. Raises 404 if not."""
    if item_type == "document":
        item = db.query(Document).filter(
            Document.id == item_id,
            Document.firm_id == firm_id,
            Document.deleted_at.is_(None),
        ).first()
    else:
        item = db.query(DocumentFolder).filter(
            DocumentFolder.id == item_id,
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.deleted_at.is_(None),
        ).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{item_type.capitalize()} not found",
        )


def add_favorite(
    db: Session,
    *,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
) -> DocumentFavorite:
    _validate_item_type(item_type)
    _assert_item_exists(db, firm_id, item_type, item_id)

    existing = db.query(DocumentFavorite).filter(
        DocumentFavorite.user_id == user_id,
        DocumentFavorite.item_type == item_type,
        DocumentFavorite.item_id == item_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already favorited",
        )

    fav = DocumentFavorite(
        firm_id=firm_id,
        user_id=user_id,
        item_type=item_type,
        item_id=item_id,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


def remove_favorite(
    db: Session,
    *,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
) -> None:
    """Idempotent -- no error if not already favorited."""
    _validate_item_type(item_type)
    db.query(DocumentFavorite).filter(
        DocumentFavorite.firm_id == firm_id,
        DocumentFavorite.user_id == user_id,
        DocumentFavorite.item_type == item_type,
        DocumentFavorite.item_id == item_id,
    ).delete(synchronize_session=False)
    db.commit()


def list_favorites(
    db: Session,
    *,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> List[dict]:
    """
    Return the user's favorites in creation order, joined against the real
    Document/DocumentFolder tables to exclude soft-deleted items and supply
    enough data (name, content_type) for list rendering without a second
    round-trip per item.
    """
    favs = (
        db.query(DocumentFavorite)
        .filter(
            DocumentFavorite.firm_id == firm_id,
            DocumentFavorite.user_id == user_id,
        )
        .order_by(DocumentFavorite.created_at)
        .all()
    )

    result = []
    for fav in favs:
        if fav.item_type == "document":
            doc = db.query(Document).filter(
                Document.id == fav.item_id,
                Document.firm_id == firm_id,
                Document.deleted_at.is_(None),
            ).first()
            if doc is None:
                continue
            result.append({
                "id": str(fav.id),
                "item_type": "document",
                "item_id": str(doc.id),
                "name": doc.filename,
                "content_type": doc.content_type,
                "created_at": fav.created_at.isoformat(),
            })
        else:
            folder = db.query(DocumentFolder).filter(
                DocumentFolder.id == fav.item_id,
                DocumentFolder.firm_id == firm_id,
                DocumentFolder.deleted_at.is_(None),
            ).first()
            if folder is None:
                continue
            result.append({
                "id": str(fav.id),
                "item_type": "folder",
                "item_id": str(folder.id),
                "name": folder.name,
                "content_type": None,
                "created_at": fav.created_at.isoformat(),
            })
    return result
