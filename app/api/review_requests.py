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
import app.services.review_request_service as review_request_service
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

    google_review_url = review_request_service.record_nps_score(
        db=db, firm=firm, score=body.score, engagement_id=body.engagement_id,
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

    review_request_service.submit_feedback(
        db=db, firm=firm, score=body.score,
        engagement_id=body.engagement_id, feedback_text=body.feedback_text,
    )

    return {"ok": True}
