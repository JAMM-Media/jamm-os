# app/api/clients.py

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from pydantic import BaseModel

from app.models.engagement import Engagement
from app.models.task import Task
from app.models.firm import Firm
from app.schemas.engagement import EngagementOut
from app.schemas.task import TaskOut
from app.db.session import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut
from app.schemas.pagination import PaginatedResponse
from app.crud import client as crud_client
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientOverview(BaseModel):
    client: ClientOut
    engagements: List[EngagementOut]
    tasks: List[TaskOut]


# ---------------------------------------------------------
# LIST
# firm_id scoping is the key security requirement here.
# We ALWAYS filter by current_firm.id — never return all clients.
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    q: Optional[str] = None,
    is_active: Optional[bool] = None,
    tags: Optional[str] = None,
    limit: int = Query(50, le=1000),
    offset: int = 0,
):
    # firm_id filter is ALWAYS applied first — this is tenant isolation.
    stmt = select(Client).where(Client.firm_id == current_firm.id)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Client.name.ilike(like),
                Client.email.ilike(like),
                Client.company_name.ilike(like),
            )
        )

    if is_active is not None:
        stmt = stmt.where(Client.is_active == is_active)

    if tags:
        stmt = stmt.where(Client.tags.ilike(f"%{tags}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    stmt = stmt.order_by(Client.created_at.desc()).offset(offset).limit(limit)
    items = db.execute(stmt).scalars().all()

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------
@router.get("/{client_id}/overview", response_model=ClientOverview)
def get_client_overview(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    engagements = db.execute(
        select(Engagement).where(
            Engagement.client_id == client_id,
            Engagement.firm_id == current_firm.id,  # Double-check firm isolation
        )
    ).scalars().all()

    tasks = db.execute(
        select(Task).where(
            Task.client_id == client_id,
            Task.firm_id == current_firm.id,  # Double-check firm isolation
        )
    ).scalars().all()

    return ClientOverview(client=client, engagements=engagements, tasks=tasks)


# ---------------------------------------------------------
# CREATE
# firm_id is taken from the JWT — never from the request body.
# This prevents a user from creating a client in another firm.
# ---------------------------------------------------------
@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    try:
        return crud_client.create_client(db, payload, firm_id=current_firm.id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A client with this email already exists.",
        )


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------
@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return crud_client.update_client(db, client, payload)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------
@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    crud_client.delete_client(db, client)