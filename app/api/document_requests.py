# app/api/document_requests.py

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.document_request import (
    DocumentRequestCreate,
    DocumentRequestOut,
    DocumentRequestUpdate,
)
from app.schemas.pagination import PaginatedResponse
from app.crud import document_request as crud
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
from app.models.user import User
import app.services.document_request_service as dr_service

router = APIRouter(prefix="/document-requests", tags=["document-requests"])


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------
@router.post("/", response_model=DocumentRequestOut, status_code=status.HTTP_201_CREATED)
def create_document_request(
    payload: DocumentRequestCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    return dr_service.create_document_request(
        db=db, payload=payload, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[DocumentRequestOut])
def list_document_requests(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items = crud.list_document_requests(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    # Re-run without pagination for total count
    total_items = crud.list_document_requests(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
        skip=0,
        limit=10_000,
    )
    return PaginatedResponse(total=len(total_items), limit=limit, offset=skip, items=items)


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/{request_id}", response_model=DocumentRequestOut)
def get_document_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    doc_request = crud.get_document_request(db, request_id, firm_id=current_firm.id)
    if not doc_request:
        raise HTTPException(status_code=404, detail="Document request not found")
    return doc_request


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------
@router.patch("/{request_id}", response_model=DocumentRequestOut)
def update_document_request(
    request_id: UUID,
    payload: DocumentRequestUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    result = dr_service.update_document_request(
        db=db, request_id=request_id, payload=payload,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Document request not found")
    return result


# ---------------------------------------------------------
# DELETE  (manager+ only)
# ---------------------------------------------------------
@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_manager_or_above),
):
    deleted = dr_service.delete_document_request(
        db=db, request_id=request_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document request not found")


# ---------------------------------------------------------
# PATCH CHECKLIST ITEM STATUS
# ---------------------------------------------------------
from pydantic import BaseModel


class ItemStatusBody(BaseModel):
    status: Literal["pending", "uploaded", "approved", "rejected"]


@router.patch("/{request_id}/items/{item_id}", response_model=DocumentRequestOut)
def update_checklist_item_status(
    request_id: UUID,
    item_id: str,
    payload: ItemStatusBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    updated, error = dr_service.update_checklist_item_status(
        db=db, request_id=request_id, item_id=item_id,
        new_status=payload.status, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )
    if error == "request_not_found":
        raise HTTPException(status_code=404, detail="Document request not found")
    if error == "item_not_found":
        raise HTTPException(status_code=400, detail=f"Item '{item_id}' not found in checklist")
    return updated
