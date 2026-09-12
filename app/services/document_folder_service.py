# app/services/document_folder_service.py

from collections import deque
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud import document_folder as crud_folder
from app.crud import document as crud_document
from app.models.document_folder import DocumentFolder
from app.models.engagement import Engagement
from app.services.document_access import assert_engagement_not_finalized


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

    assert_engagement_not_finalized(db, engagement_id)

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
    assert_engagement_not_finalized(db, folder.engagement_id)

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


def rename_folder(
    *,
    db: Session,
    folder: DocumentFolder,
    firm_id: UUID,
    name: str,
) -> DocumentFolder:
    """Rename a folder. Gated by the engagement finalize check."""
    assert_engagement_not_finalized(db, folder.engagement_id)
    return crud_folder.rename_document_folder(db, folder=folder, name=name)


def copy_folder_structure(
    *,
    db: Session,
    source_engagement_id: UUID,
    dest_engagement_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
) -> dict:
    """Copy the folder skeleton from source into dest engagement (skeleton only, no documents).

    Both engagements must belong to the same firm and the same client. The
    destination must not be finalized.

    Returns {"folders_created": int, "id_map": {str(old_id): str(new_id)}}.
    The id_map lets the caller place cherry-picked document copies into the
    correct destination folders without a separate lookup.
    """
    if source_engagement_id == dest_engagement_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source and destination engagements must be different",
        )

    src_eng = db.query(Engagement).filter(
        Engagement.id == source_engagement_id,
        Engagement.firm_id == firm_id,
    ).first()
    if not src_eng:
        raise HTTPException(status_code=404, detail="Source engagement not found")

    dest_eng = db.query(Engagement).filter(
        Engagement.id == dest_engagement_id,
        Engagement.firm_id == firm_id,
    ).first()
    if not dest_eng:
        raise HTTPException(status_code=404, detail="Destination engagement not found")

    if src_eng.client_id != dest_eng.client_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source and destination engagements must belong to the same client",
        )

    assert_engagement_not_finalized(db, dest_engagement_id)

    # Load all non-deleted folders in the source engagement.
    source_folders = db.query(DocumentFolder).filter(
        DocumentFolder.firm_id == firm_id,
        DocumentFolder.engagement_id == source_engagement_id,
        DocumentFolder.deleted_at.is_(None),
    ).order_by(DocumentFolder.name).all()

    if not source_folders:
        return {"folders_created": 0, "id_map": {}}

    # Build a children map for BFS traversal (None key = root folders).
    children_of: dict = {}
    for folder in source_folders:
        key = folder.parent_folder_id
        if key not in children_of:
            children_of[key] = []
        children_of[key].append(folder)

    # BFS from root folders outward so parents are always created before children.
    id_map: dict = {}
    folders_created = 0
    queue: deque = deque(children_of.get(None, []))

    while queue:
        src_folder = queue.popleft()

        # Remap parent_folder_id: None for roots, new id for children.
        new_parent_id = None
        if src_folder.parent_folder_id is not None:
            new_parent_id = id_map.get(src_folder.parent_folder_id)

        new_folder = crud_folder.create_document_folder(
            db=db,
            firm_id=firm_id,
            scope="engagement",
            name=src_folder.name,
            client_id=dest_eng.client_id,
            engagement_id=dest_engagement_id,
            parent_folder_id=new_parent_id,
        )

        id_map[src_folder.id] = new_folder.id
        folders_created += 1

        # Enqueue children of this source folder.
        for child in children_of.get(src_folder.id, []):
            queue.append(child)

    return {
        "folders_created": folders_created,
        "id_map": {str(old): str(new) for old, new in id_map.items()},
    }
