# app/api/clients.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from pydantic import BaseModel

from app.models.project import Project
from app.models.task import Task
from app.schemas.project import ProjectOut
from app.schemas.task import TaskOut
from app.db.session import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut

class ClientOverview(BaseModel):
    client: ClientOut
    projects: List[ProjectOut]
    tasks: List[TaskOut]

router = APIRouter(prefix="/clients", tags=["clients"])

def _tags_to_str(tags):
    if tags is None:
        return None
    return ",".join(dict.fromkeys([t.strip() for t in tags if t and t.strip()]))

@router.get("/", response_model=List[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    is_active: Optional[bool] = None,
    tags: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(Client)

    # text search
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Client.name.ilike(like),
                Client.email.ilike(like),
                Client.company_name.ilike(like),
            )
        )

    # active filter
    if is_active is not None:
        stmt = stmt.where(Client.is_active == is_active)

    # simple tag substring filter
    if tags:
        stmt = stmt.where(Client.tags.ilike(f"%{tags}%"))

    # order & paginate
    stmt = stmt.order_by(Client.created_at.desc()).offset(offset).limit(limit)

    result = db.execute(stmt)
    return result.scalars().all()

@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Client not found")
    return obj

@router.get("/{client_id}/overview", response_model=ClientOverview)
def get_client_overview(
    client_id: UUID,
    db: Session = Depends(get_db),
):
    # 1) Load the client
    client_stmt = select(Client).where(Client.id == client_id)
    client_result = db.execute(client_stmt)
    client = client_result.scalars().first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 2) Load this client's projects
    projects_stmt = select(Project).where(Project.client_id == client_id)
    projects_result = db.execute(projects_stmt)
    projects = projects_result.scalars().all()

    # 3) Load this client's tasks
    tasks_stmt = select(Task).where(Task.client_id == client_id)
    tasks_result = db.execute(tasks_stmt)
    tasks = tasks_result.scalars().all()

    return ClientOverview(
        client=client,
        projects=projects,
        tasks=tasks,
    )

@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)):
    obj = Client(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        company_name=payload.company_name,
        tax_id=payload.tax_id,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country,
        notes=payload.notes,
        is_active=True if payload.is_active is None else payload.is_active,
        tags=_tags_to_str(payload.tags),
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A client with this email already exists.",
        )
    db.refresh(obj)
    return obj

@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: UUID, payload: ClientUpdate, db: Session = Depends(get_db)):
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Client not found")

    data = payload.model_dump(exclude_unset=True)
    if "tags" in data:
        data["tags"] = _tags_to_str(data["tags"])

    for k, v in data.items():
        setattr(obj, k, v)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: UUID, db: Session = Depends(get_db)):
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(obj)
    db.commit()
    return None
