# app/api/document_expiries.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import document_expiry as crud
from app.db.session import get_db
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from app.schemas.document_expiry import (
    DocumentExpiryCreate,
    DocumentExpiryOut,
    DocumentExpiryUpdate,
)

router = APIRouter(prefix="/document-expiries", tags=["Document Expiries"])


@router.get("/", response_model=list[DocumentExpiryOut])
def list_document_expiries(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    return crud.list_for_client(db, current_firm.id, client_id)


@router.post("/", response_model=DocumentExpiryOut, status_code=status.HTTP_201_CREATED)
def create_document_expiry(
    payload: DocumentExpiryCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    client = db.execute(
        select(Client).where(
            Client.id == payload.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return crud.create(db, current_firm.id, payload)


@router.patch("/{expiry_id}", response_model=DocumentExpiryOut)
def update_document_expiry(
    expiry_id: UUID,
    payload: DocumentExpiryUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    obj = crud.get(db, current_firm.id, expiry_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Document expiry not found")
    return crud.update(db, obj, payload)


@router.delete("/{expiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_expiry(
    expiry_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    obj = crud.get(db, current_firm.id, expiry_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Document expiry not found")
    crud.delete(db, obj)
