# app/api/clients.py

import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, status, Query, UploadFile
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
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut, ClientImportResult, QBOARBalanceOut, ClientHealthOut, QBOHealthOut, QBOTrendOut, QBOCustomerIncomeOut, QBOCashFlowOut
from app.schemas.pagination import PaginatedResponse
from app.crud import client as crud_client
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.dependencies.auth import get_current_user
from app.models.user import User
import app.services.client_service as client_service

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
# CSV IMPORT
# Accepts a CSV file upload and bulk-creates clients.
# Required columns: name, email (optional), entity_type (optional)
# Optional columns: phone, company_name
# Max 500 clients per import. Deduplicates on email.
# firm_id always injected from JWT — never from the CSV.
# ---------------------------------------------------------
@router.post("/import", response_model=ClientImportResult)
async def import_clients_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    """
    Bulk import clients from a CSV file.

    Required columns: name
    Optional columns: email, entity_type, phone, company_name

    Rules:
    - Max 500 rows per import
    - Rows with no name are skipped with an error
    - Rows where email already exists for this firm are skipped (not errors)
    - entity_type must be one of: individual, business, trust, estate, non_profit
    - firm_id is always injected from JWT — never from the CSV
    """
    MAX_ROWS = 500

    # Read and decode the uploaded file
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")  # utf-8-sig handles Excel BOM
    except UnicodeDecodeError:
        try:
            text = contents.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not decode file. Please upload a UTF-8 or Latin-1 CSV.",
            )

    reader = csv.DictReader(io.StringIO(text))

    # Validate required column exists
    if reader.fieldnames is None or "name" not in [
        f.strip().lower() for f in reader.fieldnames
    ]:
        raise HTTPException(
            status_code=400,
            detail="CSV must have a 'name' column.",
        )

    # Normalize fieldnames to lowercase
    rows = []
    for row in reader:
        rows.append({k.strip().lower(): v.strip() for k, v in row.items()})

    if len(rows) > MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Import limit is {MAX_ROWS} clients per upload. "
                   f"Your file has {len(rows)} rows.",
        )

    created, skipped, errors = client_service.import_clients_csv(
        db=db, rows=rows, firm_id=current_firm.id,
    )

    return ClientImportResult(created=created, skipped=skipped, errors=errors)


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
# QBO AR BALANCE
# ---------------------------------------------------------
@router.get("/{client_id}/qbo-ar", response_model=QBOARBalanceOut)
def get_client_qbo_ar(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    from app.services.qbo_ar_service import get_qbo_ar_balance

    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.quickbooks_customer_id:
        return QBOARBalanceOut(connected=False, outstanding_balance=None, last_payment_date=None)

    result = get_qbo_ar_balance(current_firm.id, client.quickbooks_customer_id, db)
    return QBOARBalanceOut(**result)


# ---------------------------------------------------------
# QBO HEALTH
# ---------------------------------------------------------
@router.get("/{client_id}/qbo-health", response_model=QBOHealthOut)
def get_client_qbo_health(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    from app.services.qbo_health_service import get_bookkeeping_health

    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    result = get_bookkeeping_health(client, current_firm.id, db)
    return QBOHealthOut(**result)


# ---------------------------------------------------------
# QBO TRENDS
# ---------------------------------------------------------
@router.get("/{client_id}/qbo-trends", response_model=QBOTrendOut)
def get_client_qbo_trends(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    from app.services.qbo_trend_service import get_pl_and_bs_trends

    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    result = get_pl_and_bs_trends(client, current_firm.id, db)
    return QBOTrendOut(
        connected=result["connected"],
        months=result["months"],
        trends=result["trends"] if result["trends"] else {},
        checked_at=result["checked_at"],
    )


# ---------------------------------------------------------
# QBO CUSTOMER INCOME
# ---------------------------------------------------------
@router.get("/{client_id}/qbo-income", response_model=QBOCustomerIncomeOut)
def get_client_qbo_income(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    from app.services.qbo_income_cashflow_service import get_customer_income

    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    result = get_customer_income(client, current_firm.id, db)
    return QBOCustomerIncomeOut(**result)


# ---------------------------------------------------------
# QBO CASH FLOW
# ---------------------------------------------------------
@router.get("/{client_id}/qbo-cashflow", response_model=QBOCashFlowOut)
def get_client_qbo_cashflow(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    from app.services.qbo_income_cashflow_service import get_cash_flow

    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    result = get_cash_flow(client, current_firm.id, db)
    return QBOCashFlowOut(**result)


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------
@router.get("/{client_id}/health", response_model=ClientHealthOut)
def get_client_health(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    from app.services.client_health_service import compute_client_health

    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return compute_client_health(client_id, current_firm.id, db)


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
    current_user: User = Depends(get_current_user),
):
    from app.services.audit_service import write_audit_log
    new_client = client_service.create_client(
        db=db, payload=payload, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action='client.created',
        actor_id=current_user.id,
        actor_type='staff',
        entity_type='client',
        entity_id=new_client.id,
    )
    return new_client


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
    current_user: User = Depends(get_current_user),
):
    client = crud_client.get_client_for_firm(db, client_id, current_firm.id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return client_service.update_client(
        db=db, client=client, payload=payload,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------
@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    current_user: User = Depends(get_current_user),
):
    from app.services.audit_service import write_audit_log
    result = client_service.delete_client(
        db=db, client_id=client_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Client not found")
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action='client.deleted',
        actor_id=current_user.id,
        actor_type='staff',
        entity_type='client',
        entity_id=client_id,
    )