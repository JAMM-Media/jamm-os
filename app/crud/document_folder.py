# app/crud/document_folder.py

import uuid
from collections import deque
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
    system_key: Optional[str] = None,
) -> DocumentFolder:
    folder = DocumentFolder(
        firm_id=firm_id,
        scope=scope,
        name=name,
        client_id=client_id,
        engagement_id=engagement_id,
        parent_folder_id=parent_folder_id,
        system_key=system_key,
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


def get_system_folder(
    db: Session,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    system_key: str,
) -> Optional[DocumentFolder]:
    """Return the first live folder with the given system_key within an engagement."""
    return db.query(DocumentFolder).filter(
        DocumentFolder.firm_id == firm_id,
        DocumentFolder.engagement_id == engagement_id,
        DocumentFolder.system_key == system_key,
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


def get_document_folder_by_name(
    db: Session,
    firm_id: uuid.UUID,
    scope: str,
    parent_folder_id: Optional[uuid.UUID],
    name: str,
) -> Optional[DocumentFolder]:
    """Return the first live (not soft-deleted) folder matching firm, scope,
    parent, and name exactly. Used by import finalization to locate an already-
    created folder before deciding whether to create a new one, so a batch
    importing multiple files under the same path creates the shared folder only
    once. No precedent for this query exists elsewhere in this file."""
    return db.query(DocumentFolder).filter(
        DocumentFolder.firm_id == firm_id,
        DocumentFolder.scope == scope,
        DocumentFolder.parent_folder_id == parent_folder_id,
        DocumentFolder.name == name,
        DocumentFolder.deleted_at.is_(None),
    ).first()


def get_subtree_height(db: Session, folder_id: uuid.UUID, firm_id: uuid.UUID) -> int:
    """Walk downward through live children and return the number of additional levels
    below folder_id. Returns 0 if the folder has no children (leaf). Returns 1 if
    the deepest live child has no children of its own, etc.

    Used by move_folder to compute the full depth footprint of the folder's
    existing subtree before applying the MAX_FOLDER_DEPTH constraint.

    Child lookup uses the same filter as get_document_folder: live folders
    belonging to firm_id with the given parent_folder_id.
    """
    max_height = 0
    queue: deque = deque([(folder_id, 0)])
    while queue:
        current_id, level = queue.popleft()
        children = db.query(DocumentFolder).filter(
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.parent_folder_id == current_id,
            DocumentFolder.deleted_at.is_(None),
        ).all()
        for child in children:
            child_level = level + 1
            if child_level > max_height:
                max_height = child_level
            queue.append((child.id, child_level))
    return max_height


def get_descendant_folder_ids(db: Session, folder_id: uuid.UUID, firm_id: uuid.UUID) -> set:
    """Return the set of UUIDs of all live folders that are descendants of folder_id
    at any depth. Used by move_folder to build the cycle-prevention exclusion set.

    Traversal uses the same BFS child-lookup pattern as get_subtree_height. The two
    functions are kept separate rather than combined: their return types differ and
    neither is a specialisation of the other.
    """
    result: set = set()
    queue: deque = deque([folder_id])
    while queue:
        current_id = queue.popleft()
        children = db.query(DocumentFolder).filter(
            DocumentFolder.firm_id == firm_id,
            DocumentFolder.parent_folder_id == current_id,
            DocumentFolder.deleted_at.is_(None),
        ).all()
        for child in children:
            result.add(child.id)
            queue.append(child.id)
    return result
