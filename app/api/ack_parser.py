# app/api/ack_parser.py

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.dependencies.auth import get_current_user
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import EngagementStatus
from app.services.ack_parser_service import parse_ack_file
import app.services.ack_parser_service as ack_parser_service

router = APIRouter(tags=["ACK Parser"])

_MAX_FILE_BYTES = 512 * 1024  # 512 KB


class AckUploadResult(BaseModel):
    total_records: int
    matched: int
    acknowledged: int
    rejected: int
    unmatched: list[dict]


@router.post("/upload", response_model=AckUploadResult)
async def upload_ack(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    if not file.filename or not file.filename.lower().endswith(".ack"):
        raise HTTPException(status_code=400, detail="File must have a .ack extension.")

    raw = await file.read()

    if len(raw) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 512 KB limit.")

    contents = raw.decode("utf-8", errors="replace")

    try:
        records = parse_ack_file(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    matched = 0
    acknowledged_count = 0
    rejected_count = 0
    unmatched: list[dict] = []

    for record in records:
        taxpayer_id = record["taxpayer_id"]
        confirmation_number = record["confirmation_number"]
        form_type = record["form_type"]
        status = record["status"]
        tax_year = record.get("tax_year")

        client = db.execute(
            select(Client).where(
                Client.firm_id == current_firm.id,
                Client.tax_id == taxpayer_id,
            )
        ).scalars().first()

        # Tax ID used only for lookup; never referenced again after this point.
        del taxpayer_id

        if not client:
            unmatched.append({
                "confirmation_number": confirmation_number,
                "form_type": form_type,
                "reason": "no_client_match",
            })
            continue

        engagement = db.execute(
            select(Engagement)
            .where(
                Engagement.firm_id == current_firm.id,
                Engagement.client_id == client.id,
                Engagement.is_active == True,
                Engagement.status != EngagementStatus.archived.value,
            )
            .order_by(Engagement.created_at.desc())
        ).scalars().all()

        efileable = [e for e in engagement if e.is_efileable]

        if not efileable:
            unmatched.append({
                "confirmation_number": confirmation_number,
                "form_type": form_type,
                "reason": "no_efileable_engagement",
            })
            continue

        eng = efileable[0]
        eng.efiled_at = datetime.now(timezone.utc)
        eng.irs_confirmation_number = confirmation_number

        is_accepted = status == "A"
        is_rejected = status == "R"

        if is_accepted:
            eng.status = EngagementStatus.acknowledged.value
            acknowledged_count += 1
        elif is_rejected:
            rejected_count += 1

        db.commit()
        matched += 1

        ack_parser_service.record_efiled(
            db=db,
            firm_id=current_firm.id,
            engagement_id=eng.id,
            actor_id=current_user.id,
            confirmation_number=confirmation_number,
            form_type=form_type,
            status=status,
            tax_year=tax_year,
        )

    return AckUploadResult(
        total_records=len(records),
        matched=matched,
        acknowledged=acknowledged_count,
        rejected=rejected_count,
        unmatched=unmatched,
    )
