STANDING RULES
- Path comment at top of every file
- Never use && to chain commands — run each command separately
- All SQLAlchemy models use Mapped[] syntax
- Pydantic v2 only — model_dump(), field_validator()
- Tenant isolation on every query — always scoped to firm_id
- Never pass the request db session into a background task
- Routers are thin — no business logic

TASK: Client review request flow (NPS gate to Google review)

BACKGROUND
This is an upsell feature. When a firm owner or manager marks an
engagement complete, they are prompted to send the client a review
request email. The email contains a 1-10 rating scale. Clicking a
rating takes the client to a public page that:
- If score is 9 or 10: shows a prompt to leave a Google review
  with a link to the firm's Google review page
- If score is 1-8: shows a private feedback form, response is
  emailed to the firm owner

The firm must set their Google review URL in Settings before the
feature works. Staff role cannot trigger review requests — only
firm_owner and manager.

This feature is gated behind a feature flag:
  firm.feature_flags["review_requests_enabled"]
If the flag is false or missing, the prompt never appears and
the endpoints return 403.

STEP 1 — Add Google review URL to Settings

1A — Backend: In app/api/settings.py, add a new endpoint:

  PATCH /settings/review
  firm_owner only
  Body schema (add to app/schemas/settings.py):
    class ReviewSettingsUpdate(BaseModel):
        google_review_url: str | None = None
        model_config = ConfigDict(str_strip_whitespace=True)

  Logic: merge "google_review_url" into firm.settings.
  Validate that google_review_url, if provided, starts with
  "https://" — return 400 if it does not.
  Return the updated firm.settings dict.

1B — Frontend: In frontend/src/app/settings/page.tsx, add a
"Review Requests" section below the Email Settings section.
Only visible to firm_owner.

  - Text input labeled "Google Review Link"
  - Placeholder: "https://g.page/r/your-business/review"
  - Helper text: "Clients who rate their experience 9 or 10
    will be directed here to leave a public review."
  - Save button calling PATCH /settings/review
  - Success toast: "Review settings saved"
  - Load current value from firmData.settings.google_review_url
    on mount

STEP 2 — Create app/services/review_request_service.py

Create this new file:

```python
# app/services/review_request_service.py

"""
Client review request service for JAMM PX.

Sends a review request email to a client after engagement
completion. The email contains a 1-10 rating scale. High scores
(9-10) route to the firm's Google review page. Low scores (1-8)
collect private feedback sent to the firm owner.

Triggered manually by firm_owner or manager at engagement
completion. Never triggered by staff role.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.firm import Firm
from app.models.client import Client
from app.models.user import User
from app.core.enums import UserRole

logger = logging.getLogger(__name__)

REVIEW_RATING_BASE_URL = "https://app.jammpx.com/review"


def send_review_request(
    db: Session,
    firm: Firm,
    client: Client,
    engagement_id: UUID,
    requested_by: User,
) -> dict:
    """
    Send a review request email to the client.

    Validates:
    - Feature flag is enabled for this firm
    - Requesting user is firm_owner or manager
    - Client has an email address
    - Firm has a google_review_url configured in settings

    Returns { "sent": true } on success.
    Raises ValueError with a clear message on validation failure.
    """
    from app.services.email_service import EmailService

    # Feature flag check
    flags = firm.feature_flags or {}
    if not flags.get("review_requests_enabled"):
        raise ValueError(
            "Review requests are not enabled for this firm."
        )

    # Role check
    if requested_by.role not in (
        UserRole.firm_owner, UserRole.manager
    ):
        raise ValueError(
            "Only firm owners and managers can send review requests."
        )

    # Client email check
    if not client.email:
        raise ValueError(
            f"{client.name} does not have an email address on file."
        )

    # Google review URL check
    settings = firm.settings or {}
    google_review_url = settings.get("google_review_url")
    if not google_review_url:
        raise ValueError(
            "No Google review link configured. Add one in "
            "Settings → Review Requests before sending."
        )

    # Build rating buttons
    email_settings = EmailService.get_firm_email_settings(firm)
    _send_review_email(
        firm=firm,
        client=client,
        engagement_id=engagement_id,
        email_settings=email_settings,
    )

    # Log behavioral event
    from app.services.behavioral_log import log_event
    log_event(
        firm_id=firm.id,
        event_type="review_request.sent",
        entity_type="engagement",
        entity_id=engagement_id,
        actor_type="staff",
        actor_id=requested_by.id,
        metadata={
            "client_id": str(client.id),
            "client_email": client.email,
        },
    )

    return {"sent": True}


def _send_review_email(
    firm: Firm,
    client: Client,
    engagement_id: UUID,
    email_settings: dict,
) -> None:
    """Build and send the review request email to the client."""
    from app.services.email_service import EmailService

    firm_name = firm.name
    client_name = client.name.split()[0] if client.name else "there"

    rating_buttons = ""
    for i in range(1, 11):
        url = (
            f"{REVIEW_RATING_BASE_URL}"
            f"?score={i}&firm={firm.id}&engagement={engagement_id}"
        )
        rating_buttons += (
            f'<a href="{url}" style="display:inline-block;'
            f'margin:3px;padding:9px 14px;background:#1F3148;'
            f'color:#FFFFFF;text-decoration:none;border-radius:6px;'
            f'font-size:14px;font-weight:500;'
            f'font-family:Inter,sans-serif;">'
            f"{i}</a>"
        )

    html_body = f"""
    <div style="font-family:Inter,sans-serif;max-width:520px;
                margin:0 auto;padding:32px 24px;">
      <p style="font-size:15px;color:#1F3148;
                font-weight:500;margin-bottom:8px;">
        Hi {client_name},
      </p>
      <p style="font-size:14px;color:#374151;line-height:1.6;
                margin-bottom:20px;">
        It was great working with you. We'd love to hear how
        the experience went — it takes just one click.
      </p>
      <p style="font-size:14px;color:#1F3148;font-weight:500;
                margin-bottom:6px;">
        How would you rate your experience working with
        {firm_name}?
      </p>
      <p style="font-size:11px;color:#6B7280;margin-bottom:16px;">
        1 = Very poor &nbsp;&nbsp;&nbsp; 10 = Excellent
      </p>
      <div style="margin-bottom:28px;line-height:2.2;">
        {rating_buttons}
      </div>
      <p style="font-size:11px;color:#9CA3AF;line-height:1.5;">
        This takes one click and your feedback goes directly
        to the team at {firm_name}.
      </p>
    </div>
    """

    EmailService._send_raw(
        to_email=client.email,
        subject=f"How was your experience with {firm_name}?",
        html_body=html_body,
        from_name=firm_name,
        reply_to=email_settings.get("reply_to"),
        display_name=email_settings.get("display_name"),
    )
```

STEP 3 — Create the backend endpoint

Create file: app/api/review_requests.py

```python
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
```

STEP 4 — Register the router in app/main.py

Add this import alongside the other router imports:
  from app.api.review_requests import router as review_requests_router

Add this line alongside the other include_router calls:
  app.include_router(review_requests_router)

STEP 5 — Create the public review landing page

Create file: frontend/src/app/review/page.tsx

This is a public page — no auth required.
Add '/review' to PUBLIC_PATHS in frontend/middleware.ts

Page behavior:
- Read score, firm, and engagement from URL searchParams
- On mount, immediately POST to /review-requests/record-score
  with { score, firm_id: firm, engagement_id: engagement }
- While waiting for the response show a centered loading state:
  a small spinner and "One moment..." in muted text
- On response:
  - If action === "google_review": show promoter view
  - If action === "feedback_form": show detractor view
- On error: show "Something went wrong. Please try again."

Promoter view (action === "google_review"):
  Card centered on page, max-width 480px
  Heading (16px, #1F3148, weight 500): "Thank you!"
  Body (14px, #374151, line-height 1.6):
    "We really appreciate you taking the time. Would you
    mind sharing your experience on Google? It helps other
    businesses find us and only takes a moment."
  Button (full width, #1F3148 bg, white text, 8px radius,
    44px height, 15px font):
    "Leave a Google Review →"
    Opens google_review_url from the API response in a new tab
  Muted text below button (11px, #9CA3AF):
    "Thank you again for choosing [firm name if available,
    otherwise 'us']."

Detractor view (action === "feedback_form"):
  Card centered on page, max-width 480px
  Heading: "Thank you for the honest feedback."
  Body: "We're still building and your input shapes what
    we improve next. What's one thing that could have been
    better?"
  Textarea (min-height 100px, #F7F7F8 bg, 0.5px border
    #C8CDD6, 6px radius, 14px, resize vertical):
    Placeholder: "Tell us what would make the experience
    better for you..."
  Submit button (same style as promoter button):
    "Submit Feedback"
    On click: POST to /review-requests/submit-feedback with
    { score, firm_id: firm, engagement_id: engagement,
      feedback_text }
    Disabled while submitting
  On submit success: replace form content with centered text:
    "Got it — thank you." (14px, #374151)
    "Your feedback goes directly to the team." (12px, #6B7280)

Page background: #E4E6EA
Card background: #EDEEF0
Card padding: 32px
Card border-radius: 10px
Card border: 0.5px solid #C8CDD6
No sidebar, no header, no auth UI of any kind.

STEP 6 — Add the engagement completion prompt to the frontend

In the engagement detail page, find where the engagement
status is changed to "completed". This is likely a button
or dropdown that fires a PATCH /engagements/{id} call with
status: "completed".

After the engagement is successfully marked complete, if the
current user's role is firm_owner or manager AND the firm's
feature flag review_requests_enabled is true, show a modal:

Modal structure:
  Title (13px, weight 500): "Engagement Complete"
  Body (13px, #374151, line-height 1.6):
    "Would you like to send [Client Name] a review request?
    Happy clients will be directed to your Google review page."
  Two buttons right-aligned, gap 8px:
    "Skip" — ghost button, closes modal, does nothing
    "Send Request" — #1F3148 bg, white text
      On click: POST /review-requests/send with
      { client_id, engagement_id }
      On success: toast "Review request sent to [Client Name]"
      On error: toast the error message from the API response
      Close modal after either outcome

If the firm does not have review_requests_enabled or the user
is staff role, do not show the modal at all — engagement
completes silently as it does today.

To check the feature flag: the firm data is available in
the engagement detail page context. Read
firm.feature_flags?.review_requests_enabled.

To check user role: read from the auth context (currentUser.role).
Only show if role === 'firm_owner' or role === 'manager'.

STEP 7 — Verify

Confirm:
1. PATCH /settings/review endpoint exists in settings.py
2. Google Review Link input exists in settings page frontend
3. app/services/review_request_service.py exists
4. app/api/review_requests.py exists with all three endpoints
5. review_requests_router registered in main.py
6. frontend/src/app/review/page.tsx exists with promoter
   and detractor views
7. /review added to PUBLIC_PATHS in middleware.ts
8. Engagement completion modal exists in engagement detail
   page, gated by feature flag and role check

Do not run migrations.
Do not restart the server.