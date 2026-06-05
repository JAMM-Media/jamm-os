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
    - entity_type must be one of: individual, business, trust, estate
    - firm_id is always injected from JWT — never from the CSV
    """
    VALID_ENTITY_TYPES = {"individual", "business", "trust", "estate"}
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

    # Load existing emails for this firm for deduplication
    existing_emails = set(
        row[0]
        for row in db.execute(
            select(Client.email).where(
                Client.firm_id == current_firm.id,
                Client.email.isnot(None),
            )
        ).all()
        if row[0]
    )

    # Load existing names for this firm for name deduplication
    existing_names = set(
        row[0].lower().strip()
        for row in db.execute(
            select(Client.name).where(
                Client.firm_id == current_firm.id,
            )
        ).all()
        if row[0]
    )

    created = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows, start=2):  # start=2 because row 1 is the header
        name = row.get("name", "").strip()
        if not name:
            errors.append({"row": i, "reason": "Missing required field: name"})
            continue

        # Deduplicate on name
        if name.lower().strip() in existing_names:
            skipped += 1
            errors.append({"row": i, "reason": "Client with this name already exists"})
            continue

        email = row.get("email", "").strip() or None
        entity_type = row.get("entity_type", "").strip().lower() or None
        phone = row.get("phone", "").strip() or None
        company_name = row.get("company_name", "").strip() or None
        address_line1 = row.get("address_line1", "").strip() or None
        address_line2 = row.get("address_line2", "").strip() or None
        city = row.get("city", "").strip() or None
        state = row.get("state", "").strip() or None
        postal_code = row.get("postal_code", "").strip() or None
        country = row.get("country", "").strip() or None
        tags = row.get("tags", "").strip() or None
        notes = row.get("notes", "").strip() or None

        # Validate entity_type if provided
        if entity_type and entity_type not in VALID_ENTITY_TYPES:
            errors.append({
                "row": i,
                "reason": f"Invalid entity_type '{entity_type}'. "
                          f"Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
            })
            continue

        # Deduplicate on email
        if email and email.lower() in existing_emails:
            skipped += 1
            continue

        try:
            new_client = Client(
                firm_id=current_firm.id,
                name=name,
                email=email,
                entity_type=entity_type,
                phone=phone,
                company_name=company_name,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                tags=tags,
                notes=notes,
                is_active=True,
            )
            db.add(new_client)
            db.flush()  # get the ID without committing yet

            if email:
                existing_emails.add(email.lower())
            existing_names.add(name.lower().strip())

            created += 1

        except Exception as e:
            db.rollback()
            errors.append({"row": i, "reason": f"Database error: {str(e)}"})
            continue

    db.commit()

    from app.services.behavioral_log import log_event
    log_event(
        firm_id=current_firm.id,
        event_type="client.csv_import_completed",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "errors": len(errors),
            "total_rows": len(rows),
        },
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
    return client_service.create_client(
        db=db, payload=payload, firm_id=current_firm.id,
        current_user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    result = client_service.delete_client(
        db=db, client_id=client_id, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Client not found")