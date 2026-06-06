# app/api/migration.py

import csv
import io
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm

router = APIRouter(prefix="/migration", tags=["migration"])

ENTITY_TYPE_MAP = {
    "individual": "individual",
    "business": "business",
    "trust": "trust",
    "estate": "estate",
    "non-profit": "non_profit",
    "nonprofit": "non_profit",
    "non_profit": "non_profit",
}

ENGAGEMENT_STATUS_MAP = {
    "in progress": "active",
    "active": "active",
    "open": "active",
    "completed": "completed",
    "done": "completed",
    "finished": "completed",
    "draft": "draft",
    "not started": "draft",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ClientPreviewRow(BaseModel):
    row_number: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    entity_type: Optional[str] = None
    tags: Optional[str] = None
    state: Optional[str] = None
    status: str
    reason: Optional[str] = None


class ClientPreviewResult(BaseModel):
    total_rows: int
    will_import: int
    will_skip: int
    warnings: int
    rows: List[ClientPreviewRow]


class ClientImportResult(BaseModel):
    created: int
    skipped: int
    warnings: int
    errors: List[dict]


class JobPreviewRow(BaseModel):
    row_number: int
    job_name: str
    client_name: str
    client_found: bool
    mapped_status: Optional[str] = None
    filing_deadline: Optional[str] = None
    description: Optional[str] = None
    status: str
    reason: Optional[str] = None


class JobPreviewResult(BaseModel):
    total_rows: int
    will_import: int
    will_skip: int
    warnings: int
    rows: List[JobPreviewRow]


class JobImportResult(BaseModel):
    created: int
    skipped: int
    warnings: int
    errors: List[dict]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_csv_extension(file: UploadFile) -> None:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="File must be a .csv export from TaxDome.",
        )


async def _read_csv_rows(file: UploadFile) -> list[dict]:
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = contents.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not decode file. Please upload a UTF-8 or Latin-1 CSV.",
            )
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV file is empty or has no headers.")
    return [{k.strip(): (v.strip() if v else "") for k, v in row.items()} for row in reader]


def _parse_date(val: str) -> tuple[Optional[date], bool]:
    """Returns (parsed_date_or_None, had_parse_error)."""
    if not val:
        return None, False
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).date(), False
        except ValueError:
            continue
    return None, True


# ---------------------------------------------------------------------------
# ENDPOINT 1 -- preview clients
# ---------------------------------------------------------------------------

@router.post("/taxdome/preview-clients", response_model=ClientPreviewResult)
async def preview_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == current_firm.id)
        ).all()
        if r[0]
    }

    preview_rows: list[ClientPreviewRow] = []
    for i, row in enumerate(rows, start=2):
        name = row.get("Account Name", "").strip()
        if not name:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name="",
                status="warning", reason="Row skipped: Account Name is blank.",
            ))
            continue

        email = row.get("Email", "") or None
        phone = row.get("Phone", "") or None
        tags = row.get("Tags", "") or None
        state = row.get("State", "") or None
        raw_entity = row.get("Account Type", "").strip()
        entity_type = ENTITY_TYPE_MAP.get(raw_entity.lower()) if raw_entity else None

        if name.lower() in existing_names:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name=name, email=email, phone=phone,
                entity_type=entity_type, tags=tags, state=state,
                status="skip", reason="Client with this name already exists.",
            ))
            continue

        if raw_entity and raw_entity.lower() not in ENTITY_TYPE_MAP:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name=name, email=email, phone=phone,
                entity_type=None, tags=tags, state=state,
                status="warning",
                reason=f"Unknown Account Type '{raw_entity}' -- entity type will not be set.",
            ))
        else:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name=name, email=email, phone=phone,
                entity_type=entity_type, tags=tags, state=state,
                status="import",
            ))

    will_import = sum(1 for r in preview_rows if r.status == "import")
    will_skip = sum(1 for r in preview_rows if r.status == "skip")
    warnings = sum(1 for r in preview_rows if r.status == "warning")

    return ClientPreviewResult(
        total_rows=len(rows),
        will_import=will_import,
        will_skip=will_skip,
        warnings=warnings,
        rows=preview_rows,
    )


# ---------------------------------------------------------------------------
# ENDPOINT 2 -- import clients
# ---------------------------------------------------------------------------

@router.post("/taxdome/import-clients", response_model=ClientImportResult)
async def import_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == current_firm.id)
        ).all()
        if r[0]
    }

    created = 0
    skipped = 0
    warnings = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        name = row.get("Account Name", "").strip()
        if not name:
            warnings += 1
            errors.append({"row": i, "reason": "Row skipped: Account Name is blank."})
            continue

        if name.lower() in existing_names:
            skipped += 1
            continue

        email = row.get("Email", "") or None
        phone = row.get("Phone", "") or None
        tags = row.get("Tags", "") or None
        state = row.get("State", "") or None
        raw_entity = row.get("Account Type", "").strip()
        entity_type = ENTITY_TYPE_MAP.get(raw_entity.lower()) if raw_entity else None

        if raw_entity and raw_entity.lower() not in ENTITY_TYPE_MAP:
            warnings += 1
            errors.append({
                "row": i,
                "reason": f"Unknown Account Type '{raw_entity}' -- entity type not set.",
            })

        try:
            new_client = Client(
                firm_id=current_firm.id,
                name=name,
                email=email,
                phone=phone,
                entity_type=entity_type,
                tags=tags,
                state=state,
                is_active=True,
            )
            db.add(new_client)
            db.flush()
            existing_names.add(name.lower())
            created += 1
        except Exception as exc:
            db.rollback()
            errors.append({"row": i, "reason": f"Database error: {str(exc)}"})
            continue

    db.commit()

    from app.services.behavioral_log import log_event
    log_event(
        firm_id=current_firm.id,
        event_type="migration.taxdome_clients_imported",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return ClientImportResult(created=created, skipped=skipped, warnings=warnings, errors=errors)


# ---------------------------------------------------------------------------
# ENDPOINT 3 -- preview jobs
# ---------------------------------------------------------------------------

@router.post("/taxdome/preview-jobs", response_model=JobPreviewResult)
async def preview_jobs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    client_rows = db.execute(
        select(Client.id, Client.name).where(Client.firm_id == current_firm.id)
    ).all()
    client_map: dict[str, object] = {r[1].lower(): r[0] for r in client_rows if r[1]}

    preview_rows: list[JobPreviewRow] = []
    for i, row in enumerate(rows, start=2):
        job_name = row.get("Job Name", "").strip()
        client_name_raw = row.get("Client", "").strip()

        if not job_name:
            preview_rows.append(JobPreviewRow(
                row_number=i, job_name="", client_name=client_name_raw,
                client_found=False, status="warning",
                reason="Row skipped: Job Name is blank.",
            ))
            continue

        if client_name_raw.lower() not in client_map:
            preview_rows.append(JobPreviewRow(
                row_number=i, job_name=job_name, client_name=client_name_raw,
                client_found=False, status="skip",
                reason=f"No matching client found for '{client_name_raw}' -- import clients first.",
            ))
            continue

        raw_status = row.get("Status", "").strip()
        mapped_status = ENGAGEMENT_STATUS_MAP.get(raw_status.lower())
        status_warning: Optional[str] = None
        if raw_status and mapped_status is None:
            mapped_status = "draft"
            status_warning = f"Unknown status '{raw_status}' -- defaulted to draft."
        elif not raw_status:
            mapped_status = "draft"

        raw_deadline = row.get("Due Date", "").strip()
        filing_deadline_val, date_error = _parse_date(raw_deadline)
        filing_deadline_str = filing_deadline_val.isoformat() if filing_deadline_val else None
        deadline_warning: Optional[str] = (
            f"Could not parse Due Date '{raw_deadline}'." if date_error else None
        )

        description = row.get("Description", "") or None
        combined_reason = " ".join(filter(None, [status_warning, deadline_warning])) or None
        row_status = "warning" if combined_reason else "import"

        preview_rows.append(JobPreviewRow(
            row_number=i, job_name=job_name, client_name=client_name_raw,
            client_found=True, mapped_status=mapped_status,
            filing_deadline=filing_deadline_str, description=description,
            status=row_status, reason=combined_reason,
        ))

    will_import = sum(1 for r in preview_rows if r.status == "import")
    will_skip = sum(1 for r in preview_rows if r.status == "skip")
    warnings = sum(1 for r in preview_rows if r.status == "warning")

    return JobPreviewResult(
        total_rows=len(rows),
        will_import=will_import,
        will_skip=will_skip,
        warnings=warnings,
        rows=preview_rows,
    )


# ---------------------------------------------------------------------------
# ENDPOINT 4 -- import jobs
# ---------------------------------------------------------------------------

@router.post("/taxdome/import-jobs", response_model=JobImportResult)
async def import_jobs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    client_rows = db.execute(
        select(Client.id, Client.name).where(Client.firm_id == current_firm.id)
    ).all()
    client_map: dict[str, object] = {r[1].lower(): r[0] for r in client_rows if r[1]}

    created = 0
    skipped = 0
    warnings = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        job_name = row.get("Job Name", "").strip()
        client_name_raw = row.get("Client", "").strip()

        if not job_name:
            warnings += 1
            errors.append({"row": i, "reason": "Row skipped: Job Name is blank."})
            continue

        client_id = client_map.get(client_name_raw.lower())
        if client_id is None:
            skipped += 1
            errors.append({
                "row": i,
                "reason": f"No matching client found for '{client_name_raw}' -- import clients first.",
            })
            continue

        raw_status = row.get("Status", "").strip()
        mapped_status = ENGAGEMENT_STATUS_MAP.get(raw_status.lower(), "draft")
        if raw_status and raw_status.lower() not in ENGAGEMENT_STATUS_MAP:
            warnings += 1
            errors.append({"row": i, "reason": f"Unknown status '{raw_status}' -- defaulted to draft."})

        raw_deadline = row.get("Due Date", "").strip()
        filing_deadline_val, date_error = _parse_date(raw_deadline)
        if date_error:
            warnings += 1
            errors.append({"row": i, "reason": f"Could not parse Due Date '{raw_deadline}' -- deadline not set."})

        description = row.get("Description", "") or None

        try:
            new_engagement = Engagement(
                firm_id=current_firm.id,
                client_id=client_id,
                name=job_name,
                description=description,
                status=mapped_status,
                filing_deadline=filing_deadline_val,
                engagement_type=None,
                is_active=True,
            )
            db.add(new_engagement)
            db.flush()
            created += 1
        except Exception as exc:
            db.rollback()
            errors.append({"row": i, "reason": f"Database error: {str(exc)}"})
            continue

    db.commit()

    from app.services.behavioral_log import log_event
    log_event(
        firm_id=current_firm.id,
        event_type="migration.taxdome_jobs_imported",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return JobImportResult(created=created, skipped=skipped, warnings=warnings, errors=errors)


# ---------------------------------------------------------------------------
# ENDPOINT 5 -- canopy preview clients
# ---------------------------------------------------------------------------

@router.post("/canopy/preview-clients", response_model=ClientPreviewResult)
async def canopy_preview_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == current_firm.id)
        ).all()
        if r[0]
    }

    preview_rows: list[ClientPreviewRow] = []
    for i, row in enumerate(rows, start=2):
        contact_type = row.get("Contact Type", "").strip()
        row_warnings: list[str] = []

        if contact_type == "Business":
            entity_type = "business"
            name = row.get("Business Name", "").strip()
        else:
            entity_type = "individual"
            if contact_type and contact_type != "Individual":
                row_warnings.append(f"Unknown Contact Type '{contact_type}' -- defaulted to individual.")
            first = row.get("First Name", "").strip()
            last = row.get("Last Name", "").strip()
            name = f"{first} {last}".strip()

        if not name:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name="",
                status="warning", reason="Could not determine client name.",
            ))
            continue

        email = row.get("Email", "") or None
        tags = row.get("Tags", "") or None
        state = row.get("State", "") or None

        if name.lower() in existing_names:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name=name, email=email,
                entity_type=entity_type, tags=tags, state=state,
                status="skip", reason="Client with this name already exists.",
            ))
            continue

        reason = " ".join(row_warnings) or None
        status = "warning" if reason else "import"
        preview_rows.append(ClientPreviewRow(
            row_number=i, name=name, email=email,
            entity_type=entity_type, tags=tags, state=state,
            status=status, reason=reason,
        ))

    will_import = sum(1 for r in preview_rows if r.status == "import")
    will_skip = sum(1 for r in preview_rows if r.status == "skip")
    warnings = sum(1 for r in preview_rows if r.status == "warning")

    return ClientPreviewResult(
        total_rows=len(rows),
        will_import=will_import,
        will_skip=will_skip,
        warnings=warnings,
        rows=preview_rows,
    )


# ---------------------------------------------------------------------------
# ENDPOINT 6 -- canopy import clients
# ---------------------------------------------------------------------------

@router.post("/canopy/import-clients", response_model=ClientImportResult)
async def canopy_import_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == current_firm.id)
        ).all()
        if r[0]
    }

    created = 0
    skipped = 0
    warnings = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        contact_type = row.get("Contact Type", "").strip()

        if contact_type == "Business":
            entity_type = "business"
            name = row.get("Business Name", "").strip()
        else:
            entity_type = "individual"
            if contact_type and contact_type != "Individual":
                warnings += 1
                errors.append({
                    "row": i,
                    "reason": f"Unknown Contact Type '{contact_type}' -- defaulted to individual.",
                })
            first = row.get("First Name", "").strip()
            last = row.get("Last Name", "").strip()
            name = f"{first} {last}".strip()

        if not name:
            warnings += 1
            errors.append({"row": i, "reason": "Could not determine client name."})
            continue

        if name.lower() in existing_names:
            skipped += 1
            continue

        email = row.get("Email", "") or None
        tags = row.get("Tags", "") or None
        state = row.get("State", "") or None

        try:
            new_client = Client(
                firm_id=current_firm.id,
                name=name,
                email=email,
                entity_type=entity_type,
                tags=tags,
                state=state,
                is_active=True,
            )
            db.add(new_client)
            db.flush()
            existing_names.add(name.lower())
            created += 1
        except Exception as exc:
            db.rollback()
            errors.append({"row": i, "reason": f"Database error: {str(exc)}"})
            continue

    db.commit()

    from app.services.behavioral_log import log_event
    log_event(
        firm_id=current_firm.id,
        event_type="migration.canopy_clients_imported",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return ClientImportResult(created=created, skipped=skipped, warnings=warnings, errors=errors)


# ---------------------------------------------------------------------------
# ENDPOINT 7 -- karbon preview clients
# ---------------------------------------------------------------------------

@router.post("/karbon/preview-clients", response_model=ClientPreviewResult)
async def karbon_preview_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == current_firm.id)
        ).all()
        if r[0]
    }

    preview_rows: list[ClientPreviewRow] = []
    for i, row in enumerate(rows, start=2):
        name = row.get("Name", "").strip()
        if not name:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name="",
                status="warning", reason="Row skipped: Name is blank.",
            ))
            continue

        raw_type = row.get("Type", "").strip()
        row_warnings: list[str] = []
        if raw_type == "Organisation":
            entity_type = "business"
        elif raw_type == "Person":
            entity_type = "individual"
        else:
            entity_type = "individual"
            if raw_type:
                row_warnings.append(f"Unknown Type '{raw_type}' -- defaulted to individual.")

        raw_email = row.get("Email", "").strip()
        email = (raw_email.split(",")[0].strip() or None) if raw_email else None

        raw_phone = row.get("Phone", "").strip()
        phone = (raw_phone.split(",")[0].strip() or None) if raw_phone else None

        state = row.get("State/Region", "") or None

        if name.lower() in existing_names:
            preview_rows.append(ClientPreviewRow(
                row_number=i, name=name, email=email, phone=phone,
                entity_type=entity_type, state=state,
                status="skip", reason="Client with this name already exists.",
            ))
            continue

        reason = " ".join(row_warnings) or None
        status = "warning" if reason else "import"
        preview_rows.append(ClientPreviewRow(
            row_number=i, name=name, email=email, phone=phone,
            entity_type=entity_type, state=state,
            status=status, reason=reason,
        ))

    will_import = sum(1 for r in preview_rows if r.status == "import")
    will_skip = sum(1 for r in preview_rows if r.status == "skip")
    warnings = sum(1 for r in preview_rows if r.status == "warning")

    return ClientPreviewResult(
        total_rows=len(rows),
        will_import=will_import,
        will_skip=will_skip,
        warnings=warnings,
        rows=preview_rows,
    )


# ---------------------------------------------------------------------------
# ENDPOINT 8 -- karbon import clients
# ---------------------------------------------------------------------------

@router.post("/karbon/import-clients", response_model=ClientImportResult)
async def karbon_import_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    _validate_csv_extension(file)
    rows = await _read_csv_rows(file)

    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == current_firm.id)
        ).all()
        if r[0]
    }

    created = 0
    skipped = 0
    warnings = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        name = row.get("Name", "").strip()
        if not name:
            warnings += 1
            errors.append({"row": i, "reason": "Row skipped: Name is blank."})
            continue

        if name.lower() in existing_names:
            skipped += 1
            continue

        raw_type = row.get("Type", "").strip()
        if raw_type == "Organisation":
            entity_type = "business"
        elif raw_type == "Person":
            entity_type = "individual"
        else:
            entity_type = "individual"
            if raw_type:
                warnings += 1
                errors.append({
                    "row": i,
                    "reason": f"Unknown Type '{raw_type}' -- defaulted to individual.",
                })

        raw_email = row.get("Email", "").strip()
        email = (raw_email.split(",")[0].strip() or None) if raw_email else None

        raw_phone = row.get("Phone", "").strip()
        phone = (raw_phone.split(",")[0].strip() or None) if raw_phone else None

        state = row.get("State/Region", "") or None

        try:
            new_client = Client(
                firm_id=current_firm.id,
                name=name,
                email=email,
                phone=phone,
                entity_type=entity_type,
                state=state,
                is_active=True,
            )
            db.add(new_client)
            db.flush()
            existing_names.add(name.lower())
            created += 1
        except Exception as exc:
            db.rollback()
            errors.append({"row": i, "reason": f"Database error: {str(exc)}"})
            continue

    db.commit()

    from app.services.behavioral_log import log_event
    log_event(
        firm_id=current_firm.id,
        event_type="migration.karbon_clients_imported",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return ClientImportResult(created=created, skipped=skipped, warnings=warnings, errors=errors)
