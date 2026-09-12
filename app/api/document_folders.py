# app/api/document_folders.py

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.document_folder import DocumentFolderCreate, DocumentFolderOut, DocumentFolderUpdate
from app.crud import document_folder as crud_folder
from app.services.document_folder_service import create_folder, delete_folder_with_cascade, rename_folder
from app.services.document_access import assert_can_access_folder, assert_can_delete_folder

router = APIRouter(prefix="/document-folders", tags=["document-folders"])


@router.post("/", response_model=DocumentFolderOut, status_code=status.HTTP_201_CREATED)
def create_document_folder(
    payload: DocumentFolderCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Create a document folder. Any engagement member can create engagement-scoped folders."""
    from app.services.document_access import _ELEVATED
    from app.models.engagement_member import EngagementMember

    if current_user.role not in _ELEVATED and payload.scope == "engagement":
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == current_firm.id,
            EngagementMember.engagement_id == payload.engagement_id,
            EngagementMember.user_id == current_user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this engagement")
    elif current_user.role not in _ELEVATED and payload.scope in ("client", "firm_library"):
        raise HTTPException(status_code=403, detail="Manager or owner required")

    folder = create_folder(
        db=db,
        firm_id=current_firm.id,
        scope=payload.scope,
        name=payload.name,
        client_id=payload.client_id,
        engagement_id=payload.engagement_id,
        parent_folder_id=payload.parent_folder_id,
    )
    return DocumentFolderOut.model_validate(folder)


@router.get("/", response_model=list[DocumentFolderOut])
def list_document_folders(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
    scope: Optional[str] = None,
    engagement_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
    parent_folder_id: Optional[uuid.UUID] = None,
):
    folders = crud_folder.list_document_folders(
        db, firm_id=current_firm.id,
        scope=scope, engagement_id=engagement_id,
        client_id=client_id, parent_folder_id=parent_folder_id,
    )
    # Filter to only folders the user can access using the same gate function
    # as single-folder GET, so list and individual access rules stay in sync.
    accessible = []
    for f in folders:
        try:
            assert_can_access_folder(db, current_user, f, current_firm.id)
            accessible.append(f)
        except HTTPException:
            pass
    return [DocumentFolderOut.model_validate(f) for f in accessible]


@router.get("/{folder_id}", response_model=DocumentFolderOut)
def get_document_folder(
    folder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    folder = crud_folder.get_document_folder(db, folder_id=folder_id, firm_id=current_firm.id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    assert_can_access_folder(db, current_user, folder, current_firm.id)
    return DocumentFolderOut.model_validate(folder)


@router.patch("/{folder_id}", response_model=DocumentFolderOut)
def rename_document_folder(
    folder_id: uuid.UUID,
    payload: DocumentFolderUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Rename a folder. Any engagement member can rename engagement-scoped folders."""
    folder = crud_folder.get_document_folder(db, folder_id=folder_id, firm_id=current_firm.id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    assert_can_access_folder(db, current_user, folder, current_firm.id)
    updated = rename_folder(db=db, folder=folder, firm_id=current_firm.id, name=payload.name)
    return DocumentFolderOut.model_validate(updated)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_folder(
    folder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Soft-delete a folder and cascade soft-delete to its direct documents.
    Trio-gated (administrator, manager, or firm owner)."""
    folder = crud_folder.get_document_folder(db, folder_id=folder_id, firm_id=current_firm.id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    assert_can_delete_folder(db, current_user, folder, current_firm.id)
    delete_folder_with_cascade(
        db=db, folder=folder, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )

