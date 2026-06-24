# app/api/cpe_records.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud import cpe_record as crud
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner, require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.cpe_record import CPERecord
from app.models.firm import Firm
from app.models.user import User
from app.schemas.cpe_record import CPERecordCreate, CPERecordOut, CPERecordUpdate
from app.schemas.pagination import PaginatedResponse
from app.services import cpe_record_service as service
from app.core.enums import UserRole

router = APIRouter(prefix="/api/v1/cpe-records", tags=["CPE Records"])


@router.get("/", response_model=PaginatedResponse[CPERecordOut])
def list_cpe_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    total = db.execute(
        select(func.count(CPERecord.id)).where(CPERecord.firm_id == current_firm.id)
    ).scalar()
    items = crud.list_by_firm(db, current_firm.id, skip=skip, limit=limit)
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


@router.post("/", response_model=CPERecordOut, status_code=status.HTTP_201_CREATED)
def create_cpe_record(
    payload: CPERecordCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return service.create_cpe_record(db, current_firm.id, payload, current_user.id)


@router.get("/user/{user_id}", response_model=list[CPERecordOut])
def list_cpe_records_for_user(
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


@router.get("/{record_id}", response_model=CPERecordOut)
def get_cpe_record(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.firm_owner, UserRole.manager, UserRole.staff, UserRole.system_admin
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    record = crud.get(db, record_id, current_firm.id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CPE record not found")
    if current_user.role == UserRole.staff and record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return record


@router.patch("/{record_id}", response_model=CPERecordOut)
def update_cpe_record(
    record_id: UUID,
    payload: CPERecordUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return service.update_cpe_record(db, current_firm.id, record_id, payload, current_user.id)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cpe_record(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    service.delete_cpe_record(db, current_firm.id, record_id, current_user.id)
