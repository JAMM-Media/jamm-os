# app/api/firm_export.py

import io
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.services.firm_export_service import generate_firm_export_zip
import app.services.firm_export_service as firm_export_service

router = APIRouter(prefix="/firm-export", tags=["Firm Export"])


@router.post("/request-document-archive")
def request_document_archive(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    import threading
    from app.services.document_archive_service import generate_and_deliver_document_archive

    threading.Thread(
        target=generate_and_deliver_document_archive,
        kwargs={"firm_id": current_firm.id},
        daemon=True,
    ).start()

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        actor_type="user",
        action="firm.document_archive_requested",
        entity_type="firm",
        entity_id=current_firm.id,
    )

    return {"status": "processing", "message": "Your document archive is being prepared. You will receive an email with a download link shortly."}


@router.get("/download")
def download_firm_export(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    zip_bytes = generate_firm_export_zip(firm_id=current_firm.id, db=db)

    firm_export_service.record_export(
        db=db, firm_id=current_firm.id, current_user_id=current_user.id,
    )

    filename = f"jammpx_export_{date.today().isoformat()}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
