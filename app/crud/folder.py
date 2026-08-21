# app/crud/folder.py

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.folder import Folder


def create_folder(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    name: str,
    parent_folder_id: Optional[uuid.UUID] = None,
) -> Folder:
    folder = Folder(
        firm_id=firm_id,
        client_id=client_id,
        name=name,
        parent_folder_id=parent_folder_id,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def get_folder(
    db: Session,
    folder_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[Folder]:
    """Fetch a single folder scoped to the firm. Returns None if not found or wrong firm."""
    return (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.firm_id == firm_id)
        .first()
    )


def list_folders_for_client(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
) -> list[Folder]:
    """List all folders for a client, scoped to firm_id AND client_id."""
    return (
        db.query(Folder)
        .filter(Folder.firm_id == firm_id, Folder.client_id == client_id)
        .order_by(Folder.name)
        .all()
    )


def update_folder(db: Session, folder: Folder, name: str) -> Folder:
    """Rename a folder."""
    folder.name = name
    db.commit()
    db.refresh(folder)
    return folder


def delete_folder(db: Session, folder: Folder) -> None:
    """
    Delete a folder. Documents inside have their folder_id set to NULL (root)
    and child folders have their parent_folder_id set to NULL (top-level),
    both via the DB-level FK ondelete="SET NULL". Nothing is ever deleted except
    the folder row itself.
    """
    db.delete(folder)
    db.commit()
