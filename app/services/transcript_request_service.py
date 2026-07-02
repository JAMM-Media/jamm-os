# app/services/transcript_request_service.py

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crud import transcript_request as crud_transcript
from app.models.transcript_request import TranscriptRequest
from app.schemas.transcript_request import TranscriptRequestUpdate
from app.services.behavioral_log import log_event

# Terminal status values on TranscriptRequest.status. "retrieved" is success,
# "failed" is failure -- both represent the request process completing.
_TERMINAL_STATUSES = {"retrieved", "failed"}


def update_transcript_request(
    db: Session,
    request: TranscriptRequest,
    update_in: TranscriptRequestUpdate,
) -> TranscriptRequest:
    old_status = request.status

    updated = crud_transcript.update_transcript_request(db, request, update_in)

    if updated.status in _TERMINAL_STATUSES and updated.status != old_status:
        duration_days = (
            (datetime.now(timezone.utc) - updated.created_at).days
            if updated.created_at else None
        )
        log_event(
            firm_id=updated.firm_id,
            event_type="transcript_request.completed",
            entity_type="transcript_request",
            entity_id=updated.id,
            actor_type="system",
            actor_id=None,
            metadata={
                "duration_days": duration_days,
                "success": updated.status == "retrieved",
            },
        )

    return updated
