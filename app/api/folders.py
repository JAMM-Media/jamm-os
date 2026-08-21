# app/api/folders.py

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.folder import FolderCreate, FolderUpdate, FolderOut
from app.crud import folder as crud_folder

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("/", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """Create a client folder. Manager or firm_owner only."""
    return crud_folder.create_folder(
        db=db,
        firm_id=current_firm.id,
        client_id=payload.client_id,
        name=payload.name,
        parent_folder_id=payload.parent_folder_id,
    )


@router.get("/", response_model=list[FolderOut])
def list_folders(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """List all folders for a client, scoped to the current firm. Manager or firm_owner only."""
    return crud_folder.list_folders_for_client(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
    )


@router.patch("/{folder_id}", response_model=FolderOut)
def rename_folder(
    folder_id: uuid.UUID,
    payload: FolderUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """Rename a folder. Manager or firm_owner only."""
    folder = crud_folder.get_folder(db, folder_id=folder_id, firm_id=current_firm.id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return crud_folder.update_folder(db, folder=folder, name=payload.name)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """
    Delete a folder. Documents inside are moved to root (folder_id = NULL).
    Child folders become top-level (parent_folder_id = NULL).
    Manager or firm_owner only.
    """
    folder = crud_folder.get_folder(db, folder_id=folder_id, firm_id=current_firm.id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    crud_folder.delete_folder(db, folder=folder)
