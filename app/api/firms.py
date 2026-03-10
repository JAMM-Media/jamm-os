# app/api/firms.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.firm import FirmCreate, FirmUpdate, FirmOut
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import firm as crud_firm
from app.dependencies.roles import require_system_admin

router = APIRouter(prefix="/firms", tags=["firms"])


# ---------------------------------------------------------
# CREATE — system_admin only
# Only JAMM OS staff (system_admin) can create new firms.
# Firms are created when a new customer signs up.
# ---------------------------------------------------------
@router.post("/", response_model=FirmOut, status_code=status.HTTP_201_CREATED)
def create_firm(
    payload: FirmCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    existing = crud_firm.get_firm_by_slug(db, payload.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A firm with the slug '{payload.slug}' already exists.",
        )
    return crud_firm.create_firm(db, payload)


# ---------------------------------------------------------
# LIST — system_admin only
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[FirmOut])
def list_firms(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=1000),
    offset: int = 0,
    _: object = Depends(require_system_admin),
):
    query = crud_firm.get_firms(db)
    return paginate(query, limit=limit, offset=offset)


# ---------------------------------------------------------
# GET SINGLE — system_admin only
# ---------------------------------------------------------
@router.get("/{firm_id}", response_model=FirmOut)
def get_firm(
    firm_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    return firm


# ---------------------------------------------------------
# UPDATE — system_admin only
# ---------------------------------------------------------
@router.patch("/{firm_id}", response_model=FirmOut)
def update_firm(
    firm_id: UUID,
    payload: FirmUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    return crud_firm.update_firm(db, firm, payload)


# ---------------------------------------------------------
# DELETE — system_admin only
# Deleting a firm cascades to ALL its data. This is irreversible.
# ---------------------------------------------------------
@router.delete("/{firm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_firm(
    firm_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_system_admin),
):
    firm = crud_firm.get_firm(db, firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    crud_firm.delete_firm(db, firm)