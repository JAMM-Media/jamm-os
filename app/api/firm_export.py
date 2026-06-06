# app/api/firm_export.py

import io
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.services import behavioral_log
from app.services.firm_export_service import generate_firm_export_zip

router = APIRouter(prefix="/firm-export", tags=["Firm Export"])


@router.get("/download")
def download_firm_export(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    zip_bytes = generate_firm_export_zip(firm_id=current_firm.id, db=db)

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        actor_type="user",
        action="firm.data_exported",
        entity_type="firm",
        entity_id=current_firm.id,
    )

    background_tasks.add_task(
        behavioral_log.log_event,
        event_type="firm.data_exported",
        firm_id=current_firm.id,
        actor_id=current_user.id,
        actor_type="user",
    )

    filename = f"jammpx_export_{date.today().isoformat()}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
