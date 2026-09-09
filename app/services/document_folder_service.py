# app/services/document_folder_service.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import document_folder as crud_folder
from app.crud import document as crud_document
from app.models.document_folder import DocumentFolder


MAX_FOLDER_DEPTH = 20


def create_folder(
    *,
    db: Session,
    firm_id: UUID,
    scope: str,
    name: str,
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    parent_folder_id: Optional[UUID] = None,
) -> DocumentFolder:
    """Create a document folder after validating scope consistency and depth limit."""
    # Validate scope vs FK consistency.
    if scope == "engagement":
        if not engagement_id or not client_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="engagement scope requires both client_id and engagement_id",
            )
    elif scope == "client":
        if not client_id or engagement_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="client scope requires client_id and no engagement_id",
            )
    elif scope == "firm_library":
        if client_id or engagement_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="firm_library scope requires no client_id and no engagement_id",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid scope '{scope}'",
        )

    # Depth-20 tripwire: count how many ancestors the parent already has.
    if parent_folder_id is not None:
        parent = crud_folder.get_document_folder(db, folder_id=parent_folder_id, firm_id=firm_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        depth = crud_folder.get_depth(db, parent_folder_id=parent_folder_id, firm_id=firm_id)
        # depth is the depth of the parent (0 = root-level folder).
        # The new folder would be at depth + 1.
        if depth + 1 >= MAX_FOLDER_DEPTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Folder nesting cannot exceed {MAX_FOLDER_DEPTH} levels deep",
            )

    return crud_folder.create_document_folder(
        db=db,
        firm_id=firm_id,
        scope=scope,
        name=name,
        client_id=client_id,
        engagement_id=engagement_id,
        parent_folder_id=parent_folder_id,
    )


def delete_folder_with_cascade(
    *,
    db: Session,
    folder: DocumentFolder,
    firm_id: UUID,
    current_user_id: UUID,
) -> int:
    """Soft-delete a folder and cascade soft-delete to all documents directly inside it.

    Cascade scope: documents where folder_id == folder.id and deleted_at IS NULL.
    NOT recursively cascaded to child subfolders or documents inside child subfolders.
    Child subfolders retain their parent_folder_id pointing to the now-deleted folder;
    they will become orphaned references until the folder is purged (hard-deleted),
    at which point the ondelete=SET NULL cascade will null out their parent_folder_id.
    Full recursive cascade is deferred to a future task.

    Returns count of documents soft-deleted.
    """
    now = datetime.now(timezone.utc)

    # Cascade soft-delete to direct documents.
    from app.models.document import Document
    docs_in_folder = db.query(Document).filter(
        Document.firm_id == firm_id,
        Document.folder_id == folder.id,
        Document.deleted_at.is_(None),
    ).all()

    for doc in docs_in_folder:
        doc.deleted_at = now
        doc.deleted_by = current_user_id
    if docs_in_folder:
        db.flush()

    crud_folder.soft_delete_document_folder(db, folder=folder, deleted_by_id=current_user_id)

    return len(docs_in_folder)
