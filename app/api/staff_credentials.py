# app/api/staff_credentials.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud import staff_credential as crud
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner, require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.staff_credential import StaffCredential
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.staff_credential import StaffCredentialCreate, StaffCredentialOut, StaffCredentialUpdate
from app.services import staff_credential_service as service
from app.core.enums import UserRole

router = APIRouter(prefix="/api/v1/staff-credentials", tags=["Staff Credentials"])


@router.get("/", response_model=PaginatedResponse[StaffCredentialOut])
def list_credentials(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    total = db.execute(
        select(func.count(StaffCredential.id)).where(StaffCredential.firm_id == current_firm.id)
    ).scalar()
    items = crud.list_by_firm(db, current_firm.id, skip=skip, limit=limit)
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


@router.post("/", response_model=StaffCredentialOut, status_code=status.HTTP_201_CREATED)
def create_credential(
    payload: StaffCredentialCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return service.create_credential(db, current_firm.id, payload, current_user.id)


@router.get("/user/{user_id}", response_model=list[StaffCredentialOut])
def list_credentials_for_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.staff and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if current_user.role not in (
        UserRole.firm_owner, UserRole.manager, UserRole.staff, UserRole.system_admin
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return crud.list_by_user(db, current_firm.id, user_id)


@router.get("/{credential_id}", response_model=StaffCredentialOut)
def get_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.firm_owner, UserRole.manager, UserRole.staff, UserRole.system_admin
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    credential = crud.get(db, credential_id, current_firm.id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    if current_user.role == UserRole.staff and credential.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return credential


@router.patch("/{credential_id}", response_model=StaffCredentialOut)
def update_credential(
    credential_id: UUID,
    payload: StaffCredentialUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return service.update_credential(db, current_firm.id, credential_id, payload, current_user.id)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    service.delete_credential(db, current_firm.id, credential_id, current_user.id)
