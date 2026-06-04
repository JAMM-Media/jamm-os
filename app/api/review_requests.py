# app/api/review_requests.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above
from app.models.firm import Firm
from app.models.client import Client
from app.models.user import User
from app.services.review_request_service import send_review_request
from app.services.behavioral_log import log_event
from app.core.rate_limit import limiter

router = APIRouter(prefix="/review-requests", tags=["review-requests"])


class SendReviewRequestBody(BaseModel):
    client_id: UUID
    engagement_id: UUID


class RecordScoreBody(BaseModel):
    score: int
    firm_id: UUID
    engagement_id: UUID


class SubmitFeedbackBody(BaseModel):
    score: int
    firm_id: UUID
    engagement_id: UUID
    feedback_text: str


@router.post("/send")
def send_review(
    body: SendReviewRequestBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """Send a review request email to a client. Manager or above only."""
    client = db.query(Client).filter(
        Client.id == body.client_id,
        Client.firm_id == current_firm.id,
        Client.is_active == True,
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        result = send_review_request(
            db=db,
            firm=current_firm,
            client=client,
            engagement_id=body.engagement_id,
            requested_by=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.post("/record-score")
@limiter.limit("20/hour")
def record_score(
    request: Request,
    body: RecordScoreBody,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — no auth. Called when client clicks a
    rating number in the review request email.
    Records the score to firm.settings and returns routing
    instructions to the frontend.
    """
    if not (1 <= body.score <= 10):
        raise HTTPException(
            status_code=400, detail="Score must be between 1 and 10"
        )

    firm = db.query(Firm).filter(Firm.id == body.firm_id).first()
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    settings = firm.settings or {}
    google_review_url = settings.get("google_review_url", "")

    # Merge score into settings
    firm.settings = {**settings, "last_nps_score": body.score}
    db.commit()

    log_event(
        firm_id=firm.id,
        event_type="review_request.score_recorded",
        entity_type="engagement",
        entity_id=body.engagement_id,
        actor_type="client",
        actor_id=None,
        metadata={
            "score": body.score,
            "engagement_id": str(body.engagement_id),
        },
    )

    # Return routing decision to frontend
    if body.score >= 9:
        return {
            "action": "google_review",
            "google_review_url": google_review_url,
        }
    else:
        return {"action": "feedback_form"}


@router.post("/submit-feedback")
@limiter.limit("10/hour")
def submit_feedback(
    request: Request,
    body: SubmitFeedbackBody,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — no auth. Receives private feedback from
    clients who rated 1-8. Emails the feedback to the firm owner.
    """
    if not (1 <= body.score <= 10):
        raise HTTPException(
            status_code=400, detail="Score must be between 1 and 10"
        )

    firm = db.query(Firm).filter(Firm.id == body.firm_id).first()
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    # Email feedback to firm owner
    try:
        from app.services.email_service import EmailService
        from app.models.user import User
        from app.core.enums import UserRole
        from sqlalchemy import select

        owner = db.execute(
            select(User).where(
                User.firm_id == firm.id,
                User.role == UserRole.firm_owner,
                User.is_active == True,
            )
        ).scalar_one_or_none()

        if owner and owner.email:
            email_settings = EmailService.get_firm_email_settings(firm)
            html = f"""
            <div style="font-family:Inter,sans-serif;
                        max-width:520px;margin:0 auto;padding:24px;">
              <p style="font-size:14px;color:#1F3148;font-weight:500;">
                Client feedback received
              </p>
              <p style="font-size:13px;color:#374151;">
                <strong>Score:</strong> {body.score}/10
              </p>
              <p style="font-size:13px;color:#374151;">
                <strong>Feedback:</strong>
              </p>
              <p style="font-size:13px;color:#374151;
                        background:#EDEEF0;padding:12px;
                        border-radius:6px;line-height:1.6;">
                {body.feedback_text}
              </p>
              <p style="font-size:11px;color:#9CA3AF;margin-top:16px;">
                This feedback was submitted privately and was not
                posted publicly.
              </p>
            </div>
            """
            EmailService._send_raw(
                to_email=owner.email,
                subject=f"Client feedback — {body.score}/10",
                html_body=html,
                from_name="JAMM PX",
                reply_to=email_settings.get("reply_to"),
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            "Failed to email feedback to firm owner: %s", str(e)
        )

    log_event(
        firm_id=firm.id,
        event_type="review_request.feedback_submitted",
        entity_type="engagement",
        entity_id=body.engagement_id,
        actor_type="client",
        actor_id=None,
        metadata={
            "score": body.score,
            "feedback_length": len(body.feedback_text),
        },
    )

    return {"ok": True}
