# app/services/migration_service.py

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.engagement import Engagement
from app.services.behavioral_log import log_event

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


def parse_date(val: str) -> tuple[Optional[date], bool]:
    """Returns (parsed_date_or_None, had_parse_error)."""
    if not val:
        return None, False
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).date(), False
        except ValueError:
            continue
    return None, True


def import_taxdome_clients(*, db: Session, rows: list, firm_id):
    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == firm_id)
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
                firm_id=firm_id,
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

    log_event(
        firm_id=firm_id,
        event_type="migration.taxdome_clients_imported",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return created, skipped, warnings, errors


def import_taxdome_jobs(*, db: Session, rows: list, firm_id):
    client_rows = db.execute(
        select(Client.id, Client.name).where(Client.firm_id == firm_id)
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
        filing_deadline_val, date_error = parse_date(raw_deadline)
        if date_error:
            warnings += 1
            errors.append({"row": i, "reason": f"Could not parse Due Date '{raw_deadline}' -- deadline not set."})

        description = row.get("Description", "") or None

        try:
            new_engagement = Engagement(
                firm_id=firm_id,
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

    log_event(
        firm_id=firm_id,
        event_type="migration.taxdome_jobs_imported",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return created, skipped, warnings, errors


def import_canopy_individuals(*, db: Session, rows: list, firm_id):
    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == firm_id)
        ).all()
        if r[0]
    }

    created = 0
    skipped = 0
    warnings = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        first = row.get("First Name", "").strip()
        last = row.get("Last Name", "").strip()
        name = f"{first} {last}".strip()

        if not name:
            warnings += 1
            errors.append({"row": i, "reason": "Row skipped: name is blank after combining First Name and Last Name."})
            continue

        if name.lower() in existing_names:
            skipped += 1
            continue

        email = row.get("Email", "") or None
        phone = row.get("Phone", "") or None
        address_line1 = row.get("Street 1", "") or None
        address_line2 = row.get("Street 2", "") or None
        city = row.get("City", "") or None
        state = row.get("State", "") or None
        postal_code = row.get("Zip", "") or None
        country = row.get("Country", "") or None
        tags = row.get("Tags", "") or None

        try:
            new_client = Client(
                firm_id=firm_id,
                name=name,
                email=email,
                phone=phone,
                entity_type="individual",
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                tags=tags,
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

    log_event(
        firm_id=firm_id,
        event_type="migration.canopy_individuals_imported",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return created, skipped, warnings, errors


def import_canopy_businesses(*, db: Session, rows: list, firm_id):
    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == firm_id)
        ).all()
        if r[0]
    }

    created = 0
    skipped = 0
    warnings = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, start=2):
        name = row.get("Business Name", "").strip()

        if not name:
            warnings += 1
            errors.append({"row": i, "reason": "Row skipped: Business Name is blank."})
            continue

        if name.lower() in existing_names:
            skipped += 1
            continue

        email = row.get("Email", "") or None
        phone = row.get("Phone", "") or None
        address_line1 = row.get("Street 1", "") or None
        address_line2 = row.get("Street 2", "") or None
        city = row.get("City", "") or None
        state = row.get("State", "") or None
        postal_code = row.get("Zip", "") or None
        country = row.get("Country", "") or None
        tags = row.get("Tags", "") or None

        try:
            new_client = Client(
                firm_id=firm_id,
                name=name,
                email=email,
                phone=phone,
                entity_type="business",
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                tags=tags,
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

    log_event(
        firm_id=firm_id,
        event_type="migration.canopy_businesses_imported",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return created, skipped, warnings, errors


def import_karbon_clients(*, db: Session, rows: list, firm_id):
    existing_names = {
        r[0].lower()
        for r in db.execute(
            select(Client.name).where(Client.firm_id == firm_id)
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
                firm_id=firm_id,
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

    log_event(
        firm_id=firm_id,
        event_type="migration.karbon_clients_imported",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "warnings": warnings,
            "total_rows": len(rows),
        },
    )

    return created, skipped, warnings, errors
