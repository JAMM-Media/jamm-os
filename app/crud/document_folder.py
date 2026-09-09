# app/crud/document_folder.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document_folder import DocumentFolder


def create_document_folder(
    db: Session,
    firm_id: uuid.UUID,
    scope: str,
    name: str,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    parent_folder_id: Optional[uuid.UUID] = None,
) -> DocumentFolder:
    folder = DocumentFolder(
        firm_id=firm_id,
        scope=scope,
        name=name,
        client_id=client_id,
        engagement_id=engagement_id,
        parent_folder_id=parent_folder_id,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def get_document_folder(
    db: Session,
    folder_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[DocumentFolder]:
    """Return a live (not soft-deleted) folder."""
    return db.query(DocumentFolder).filter(
        DocumentFolder.id == folder_id,
        DocumentFolder.firm_id == firm_id,
        DocumentFolder.deleted_at.is_(None),
    ).first()


def get_document_folder_any_state(
    db: Session,
    folder_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[DocumentFolder]:
    """Return a folder regardless of soft-delete state."""
    return db.query(DocumentFolder).filter(
        DocumentFolder.id == folder_id,
        DocumentFolder.firm_id == firm_id,
    ).first()


def list_document_folders(
    db: Session,
    firm_id: uuid.UUID,
    scope: Optional[str] = None,
    engagement_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
    parent_folder_id: Optional[uuid.UUID] = None,
) -> list:
    """List live (not soft-deleted) document folders."""
    query = db.query(DocumentFolder).filter(
        DocumentFolder.firm_id == firm_id,
        DocumentFolder.deleted_at.is_(None),
    )
    if scope:
        query = query.filter(DocumentFolder.scope == scope)
    if engagement_id:
        query = query.filter(DocumentFolder.engagement_id == engagement_id)
    if client_id:
        query = query.filter(DocumentFolder.client_id == client_id)
    if parent_folder_id is not None:
        query = query.filter(DocumentFolder.parent_folder_id == parent_folder_id)
    return query.order_by(DocumentFolder.name).all()


def rename_document_folder(
    db: Session,
    folder: DocumentFolder,
    name: str,
) -> DocumentFolder:
    folder.name = name
    db.commit()
    db.refresh(folder)
    return folder


def soft_delete_document_folder(
    db: Session,
    folder: DocumentFolder,
    deleted_by_id: uuid.UUID,
) -> None:
    """Soft-delete a folder. Does not cascade -- caller is responsible for cascading."""
    folder.deleted_at = datetime.now(timezone.utc)
    folder.deleted_by = deleted_by_id
    db.commit()


def get_document_folder_by_name(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    name: str,
) -> Optional[DocumentFolder]:
    """Return the first live folder matching exactly this name within an engagement."""
    return db.query(DocumentFolder).filter(
        DocumentFolder.firm_id == firm_id,
        DocumentFolder.engagement_id == engagement_id,
        DocumentFolder.name == name,
        DocumentFolder.deleted_at.is_(None),
    ).first()


def get_depth(db: Session, parent_folder_id: Optional[uuid.UUID], firm_id: uuid.UUID) -> int:
    """Walk the parent chain and return the depth of parent_folder_id (0 = root child).
    Used for the depth-20 tripwire."""
    depth = 0
    current_id = parent_folder_id
    while current_id is not None:
        folder = get_document_folder(db, folder_id=current_id, firm_id=firm_id)
        if folder is None:
            break
        depth += 1
        current_id = folder.parent_folder_id
        if depth > 20:
            break
    return depth
