# app/services/irs_auth_service.py
"""
Business logic for IRS authorization forms (8821 and 2848).

PDF generation produces a clearly-marked stub PDF using weasyprint.
A real pre-filled IRS form requires IRS e-Services credentials
obtained post-launch. The stub contains all client and firm data
so the end-to-end flow is fully testable.
"""

import io
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.enums import NotificationChannel, NotificationEventType
from app.crud import irs_authorization as crud_auth
from app.crud import irs_authorization_warning as crud_warning
from app.crud import notification_preference as crud_notification_preference
from app.crud import signature_envelope as crud_envelope
from app.models.client import Client
from app.models.firm import Firm
from app.schemas.irs_authorization import (
    IrsAuthorizationCreate,
    IrsAuthorizationSendRequest,
    IrsAuthorizationUpdate,
)
from app.schemas.irs_authorization_warning import IrsAuthorizationWarningCreate
from app.schemas.signature_envelope import SignatureEnvelopeCreate
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


FORM_DESCRIPTIONS = {
    "8821": "Tax Information Authorization",
    "2848": "Power of Attorney and Declaration of Representative",
}


# Days before valid_until at which a warning fires. 0 is the expiry date
# itself. Fixed. Not configurable, and never seasonally adjusted. Firm
# authored per-type schedules are Phase B, and irs_authorization_warnings
# already has the shape to support them.
WARNING_TIERS = (60, 30, 7, 0)


# AUTHOR-SET. The system never derives a season boundary on its own.
# Each entry is ((start_month, start_day), (end_month, end_day)), inclusive
# on both ends. This matches is_tax_season() in app/api/concierge/triggers.py,
# which is the existing authored definition of filing season in this codebase.
# Changing these is an editorial decision, not a calculation.
SEASONAL_WINDOWS = (
    ((1, 15), (4, 20)),
)


def _is_in_season(day: date) -> bool:
    """
    True when day falls inside an author-set seasonal window.

    The parameter is deliberately named neutrally. The copy asks whether the
    EXPIRY date lands in filing season, not whether today does, and naming
    this as_of is what invited the wrong argument being passed once already.
    """
    for (start_month, start_day), (end_month, end_day) in SEASONAL_WINDOWS:
        start = date(day.year, start_month, start_day)
        end = date(day.year, end_month, end_day)
        if start <= day <= end:
            return True
    return False


# Warnings at this tier or nearer name what the firm loses. Further out, the
# date is the message; this close, the stakes are.
CONSEQUENCE_FROM_DAYS_REMAINING = 7


def _format_expiry_date(value: date, as_of: date) -> str:
    """
    'March 20', or 'March 20, 2025' when the date is not in the current year.

    The lapsed query has no lower bound by design, so its first run picks up
    a backlog. "expired September 8, 400 days ago" without a year is a
    confusing sentence. Written out rather than using %-d, which is not
    portable to Windows.
    """
    if value.year != as_of.year:
        return f"{value:%B} {value.day}, {value.year}"
    return f"{value:%B} {value.day}"


def _build_consequence_sentence(authorization) -> str:
    """
    What the firm actually loses.

    The transcript gate in transcript_service.request_transcript now passes on
    either form type, so an expiring 2848 can also cost transcript access,
    but only when it is the client's sole active authorization. This function
    is handed one authorization and no session, so it cannot know whether the
    other form type is still active, and it will not go looking: a warning
    that asserts lost transcript access when a live 8821 is sitting right
    there would be false. Each sentence therefore names only what the form
    itself carries, which is true of that form unconditionally.

    This is JAMM describing its own behavior, not an inference about the
    firm, which is why it is allowed to appear at all.
    """
    if authorization.form_type == "8821":
        return "Transcript access for this client stops until a new one is signed."
    return "Representation authority for this client ends until a new one is signed."


def build_expiry_warning_message(authorization, as_of: date) -> tuple[str, str]:
    """
    Build the (title, body) for an expiry warning.

    A function of the authorization and the date, never a hardcoded string
    and never a dict lookup keyed on tier alone.

    The body is COMPOSED, not formatted as one string, and that shape is
    load bearing. It is three slots:

        fact         always renders. Calendar arithmetic only.
        evidence     always None today. This is the seam.
        consequence  renders at tier 7 and nearer.

    The evidence slot is where a real, earned observation goes once one
    exists: firm memory saying how long this firm's last renewals actually
    took, or cross-firm data on renewal times. Until such data exists the
    slot stays empty. Do not fill it with a guess, and do not give this
    function a database session or an evidence provider to fetch one. When
    the data is real, this becomes a parameter change rather than a rewrite.

    Copy rules, which are hard limits:
      - Calendar fact only. Nothing inferred about the firm.
      - No percentages, no utilization figures, no volume comparisons, and
        no cohort or peer language of any kind.
      - No claim about how long a renewal takes or whether there is time to
        complete one. JAMM has never watched this firm renew anything and
        has no cross-firm data on renewal times. Asserting that 30 or 60
        days is "room" is an unearned inference, and a compliance warning is
        the worst possible venue for one.
      - Naming the season is allowed. It is pure calendar arithmetic and it
        tells the owner why the date carries more weight, without claiming
        anything about their ability to act on it.
    """
    valid_until = authorization.valid_until
    days_remaining = (valid_until - as_of).days
    expiry_date = _format_expiry_date(valid_until, as_of)
    form_label = f"Form {authorization.form_type}"

    # The season of the EXPIRY DATE, not of today. The sentence makes a claim
    # about when the authorization lapses, so asking whether today is in
    # season would produce a false statement whenever the two differ: an
    # April 18 warning about a June 17 expiry would say June 17 is in filing
    # season, and a December 20 warning about a February 18 expiry would say
    # nothing at all, staying silent exactly when the expiry lands mid-crunch.
    season_clause = ", during filing season" if _is_in_season(valid_until) else ""

    if days_remaining < 0:
        days_ago = abs(days_remaining)
        day_word = "day" if days_ago == 1 else "days"
        title = f"{form_label} has expired"
        # No season clause once it has lapsed. The season is irrelevant to an
        # authorization that is already dead, and "expired September 8, 2025,
        # 400 days ago, during filing season" is a strange sentence whichever
        # date the clause refers to.
        fact = (
            f"This authorization expired {expiry_date}, "
            f"{days_ago} {day_word} ago."
        )
    elif days_remaining == 0:
        title = f"{form_label} expires today"
        fact = f"This authorization expires today, {expiry_date}{season_clause}."
    else:
        day_word = "day" if days_remaining == 1 else "days"
        title = f"{form_label} expires in {days_remaining} {day_word}"
        fact = (
            f"This authorization expires {expiry_date}, "
            f"{days_remaining} {day_word} from today{season_clause}."
        )

    # The seam. Stays None until there is a real observation to put here.
    evidence = None

    consequence = None
    if days_remaining <= CONSEQUENCE_FROM_DAYS_REMAINING:
        consequence = _build_consequence_sentence(authorization)

    body = " ".join(part for part in (fact, evidence, consequence) if part)
    return title, body


def generate_auth_stub_pdf(
    firm: Firm,
    client: Client,
    form_type: str,
    tax_years: list[int],
    valid_from: Optional[date],
    valid_until: Optional[date],
) -> bytes:
    """Generate a stub PDF for the IRS authorization form."""
    form_name = FORM_DESCRIPTIONS.get(form_type, f"IRS Form {form_type}")
    years_str = ", ".join(str(y) for y in sorted(tax_years)) if tax_years else "Not specified"
    valid_from_str = valid_from.isoformat() if valid_from else "Effective immediately"
    valid_until_str = valid_until.isoformat() if valid_until else "Indefinite"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    logo_url = None
    firm_settings = firm.settings or {} if firm.settings else {}
    s3_key = firm_settings.get("portal_logo_s3_key")
    if s3_key:
        try:
            from app.services.s3 import generate_presigned_url
            logo_url = generate_presigned_url(s3_key)
        except Exception:
            pass

    logo_block = (
        f'<img src="{logo_url}" style="max-height:50px;width:auto;'
        f'display:block;margin-bottom:8px;" />'
        if logo_url else
        f'<h1>{firm.name}</h1>'
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; margin: 40px; color: #111111; }}
  h1 {{ font-size: 18px; font-weight: bold; margin-bottom: 4px; }}
  h2 {{ font-size: 14px; font-weight: bold; margin-top: 24px; margin-bottom: 8px;
        border-bottom: 1px solid #C8CDD6; padding-bottom: 4px; }}
  .stub-banner {{ background: #FEF3C7; border: 1px solid #F59E0B; padding: 10px 16px;
                  border-radius: 6px; margin-bottom: 24px; font-size: 11px; color: #92400E; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
  td {{ padding: 6px 8px; vertical-align: top; }}
  td:first-child {{ font-weight: bold; width: 40%; color: #6B7280; }}
  .sig-block {{ border: 1px solid #C8CDD6; padding: 16px; border-radius: 6px; margin-top: 32px; }}
  .sig-line {{ border-bottom: 1px solid #111111; margin-top: 32px; margin-bottom: 4px; }}
  .footer {{ margin-top: 40px; font-size: 10px; color: #9CA3AF; }}
</style></head>
<body>
  {logo_block}
  <h2 style="margin-top:4px;">IRS Form {form_type} — {form_name}</h2>
  <p style="color:#6B7280;font-size:11px;">Prepared by JAMM PX · {generated_at}</p>
  <div class="stub-banner">
    &#9888; STUB DOCUMENT — Review all information below before signing.
    The final IRS-formatted form will be submitted after signature collection.
  </div>
  <h2>Taxpayer Information</h2>
  <table>
    <tr><td>Name</td><td>{client.name}</td></tr>
    <tr><td>Primary Email</td><td>{getattr(client, 'primary_email', None) or 'Not on file'}</td></tr>
  </table>
  <h2>Representative (Firm)</h2>
  <table>
    <tr><td>Firm Name</td><td>{firm.name}</td></tr>
  </table>
  <h2>Authorization Details</h2>
  <table>
    <tr><td>Form Type</td><td>Form {form_type} — {form_name}</td></tr>
    <tr><td>Tax Years Covered</td><td>{years_str}</td></tr>
    <tr><td>Effective From</td><td>{valid_from_str}</td></tr>
    <tr><td>Expires</td><td>{valid_until_str}</td></tr>
  </table>
  <div class="sig-block">
    <p><strong>Taxpayer Signature</strong></p>
    <p style="font-size:11px;color:#6B7280;">
      By signing, I authorize the firm named above to act on my behalf
      as described in IRS Form {form_type}.
    </p>
    <div class="sig-line"></div>
    <p style="font-size:11px;">Signature &nbsp;&nbsp;&nbsp; Date _______________</p>
  </div>
  <div class="footer">Generated by JAMM PX Practice Management Platform.</div>
</body></html>"""

    try:
        import weasyprint
        return weasyprint.HTML(string=html).write_pdf()
    except Exception:
        return html.encode("utf-8")


def send_irs_authorization(
    db: Session,
    request: IrsAuthorizationSendRequest,
    firm: Firm,
    client: Client,
    sent_by_user_id: uuid.UUID,
) -> dict:
    """
    Full send flow for an IRS authorization form.
    Returns: {"authorization": IrsAuthorization, "envelope": SignatureEnvelope}
    """
    # 1. Generate PDF
    pdf_bytes = generate_auth_stub_pdf(
        firm=firm,
        client=client,
        form_type=request.form_type,
        tax_years=request.tax_years,
        valid_from=request.valid_from,
        valid_until=request.valid_until,
    )

    # 2. Upload to S3
    file_key = f"{firm.id}/{client.id}/irs-auth/{request.form_type}-{uuid.uuid4()}.pdf"
    try:
        s3_service.upload_fileobj(
            fileobj=io.BytesIO(pdf_bytes),
            s3_key=file_key,
            content_type="application/pdf",
        )
    except Exception:
        file_key = f"stub/{firm.id}/{request.form_type}-pending.pdf"

    # 3. Create IrsAuthorization record
    auth_create = IrsAuthorizationCreate(
        client_id=client.id,
        form_type=request.form_type,
        tax_years=request.tax_years,
        valid_from=request.valid_from,
        valid_until=request.valid_until,
    )
    authorization = crud_auth.create_irs_authorization(
        db=db, auth_in=auth_create, firm_id=firm.id
    )

    # Log authorization created
    log_event(
        firm_id=authorization.firm_id,
        event_type="irs_authorization.created",
        entity_type="irs_authorization",
        entity_id=authorization.id,
        actor_type="staff",
        actor_id=sent_by_user_id,
        metadata={
            "form_type": str(authorization.form_type) if authorization.form_type else None,
            # The model field is valid_until. The old hasattr(authorization,
            # 'expiry_date') guard was always False, so this always logged None.
            "expiry_date": authorization.valid_until.isoformat() if authorization.valid_until else None,
            "client_id": str(authorization.client_id),
        }
    )

    # 5. Create SignatureEnvelope
    form_description = FORM_DESCRIPTIONS.get(request.form_type, f"IRS Form {request.form_type}")
    signer_email = getattr(client, "primary_email", None) or ""

    envelope_create = SignatureEnvelopeCreate(
        client_id=client.id,
        engagement_id=None,
        document_id=None,
        signers=[{"name": client.name, "email": signer_email, "status": "pending"}],
        subject=f"Please sign: IRS Form {request.form_type} — {form_description}",
        message=(
            f"{firm.name} is requesting your signature on "
            f"IRS Form {request.form_type} ({form_description})."
        ),
    )
    envelope = crud_envelope.create_signature_envelope(
        db=db, schema=envelope_create, firm_id=firm.id
    )

    # 6. Link envelope to authorization
    crud_auth.update_irs_authorization(
        db=db,
        auth=authorization,
        auth_in=IrsAuthorizationUpdate(signature_envelope_id=envelope.id),
    )

    # 7. Attempt Dropbox Sign send (graceful failure)
    try:
        from app.services import dropbox_sign
        dropbox_sign.send_signature_request(
            envelope_id=str(envelope.id),
            signers=[{"name": client.name, "email_address": signer_email}],
            file_bytes=pdf_bytes,
            subject=envelope_create.subject,
            message=envelope_create.message or "",
        )
    except Exception:
        pass  # Credentials not configured — envelope stays draft

    # 8. Audit log
    write_audit_log(
        db=db,
        firm_id=firm.id,
        actor_id=sent_by_user_id,
        action=f"irs_authorization.sent.{request.form_type}",
        entity_type="irs_authorization",
        entity_id=authorization.id,
    )

    return {
        "authorization": authorization,
        "envelope": envelope,
    }


def _deliver_expiry_warning(
    *,
    db: Session,
    authorization,
    as_of: date,
) -> bool:
    """
    Send one warning to every firm_owner and manager in the firm.

    Returns True if the in-app record was written for at least one recipient,
    which is what the caller gates the warning row on.

    The sweep delivers directly rather than through the automation engine or
    the event bus. is_enabled on a preset is a toggle a firm owner can flip,
    and the two action handlers no-op on this payload anyway. A compliance
    warning a user can silently switch off, or that fails invisibly on a
    missing payload key, is not acceptable for this feature.
    """
    from app.core.enums import NotificationType, NotificationTier, RecipientType
    from app.crud import user as crud_user
    from app.services.notification_service import NotificationService

    recipients = crud_user.get_firm_owners_and_managers(db, authorization.firm_id)
    if not recipients:
        # Pathological: every firm has an owner. Do not write a warning row
        # for a tier that reached nobody, even though that means retrying
        # tomorrow. A row must mean a warning was actually delivered.
        logger.warning(
            "IRS expiry warning had no firm_owner or manager recipients: firm=%s auth=%s",
            authorization.firm_id, authorization.id,
        )
        return False

    title, body = build_expiry_warning_message(authorization, as_of)

    # send_notification_email builds its subject as "[{firm_name}] {title}",
    # so an empty firm_name ships "[] Form 8821 expires in 60 days".
    firm = db.execute(
        select(Firm).where(Firm.id == authorization.firm_id)
    ).scalars().first()
    firm_name = firm.name if firm else ""

    delivered_in_app = False
    for recipient in recipients:
        # In-app first, and unconditionally. A firm may stop the emails. A
        # firm may not make the compliance record disappear from the app.
        # The return value is the gate: create_notification is
        # Optional[Notification] and the warning row may only be written if
        # a record actually landed, not merely because a call was attempted.
        notification = NotificationService.create_notification(
            db=db,
            firm_id=authorization.firm_id,
            recipient_id=recipient.id,
            recipient_type=RecipientType.staff,
            title=title,
            body=body,
            notification_type=NotificationType.irs_auth_expiry,
            tier=NotificationTier.quiet,
            related_entity_type="irs_authorization",
            related_entity_id=authorization.id,
            force_in_app=True,
        )
        if notification is not None:
            delivered_in_app = True

    if not delivered_in_app:
        logger.warning(
            "IRS expiry warning wrote no in-app record: firm=%s auth=%s",
            authorization.firm_id, authorization.id,
        )
        return False

    # Email last, best effort, and it DOES respect the recipient's channel
    # preference. EmailService._send raises on a Postmark failure and
    # send_notification_email does not catch it, so one bad address would
    # otherwise abort every remaining recipient.
    for recipient in recipients:
        if not recipient.email:
            continue
        try:
            channel = crud_notification_preference.get_channel_for_event(
                db,
                authorization.firm_id,
                recipient.id,
                RecipientType.staff,
                NotificationEventType.irs_auth_expiry,
            )
            if channel not in (NotificationChannel.email, NotificationChannel.both):
                continue
            EmailService.send_notification_email(
                to_email=recipient.email,
                firm_name=firm_name,
                recipient_name=recipient.full_name or "",
                title=title,
                body=body,
            )
        except Exception:
            logger.exception(
                "IRS expiry warning email failed: firm=%s auth=%s recipient=%s",
                authorization.firm_id, authorization.id, recipient.id,
            )

    return True


def _record_warning_sent(
    *,
    db: Session,
    authorization,
    threshold_days: int,
    as_of: date,
) -> None:
    """Write the warning row. Only ever called after a successful send."""
    crud_warning.create_warning(
        db=db,
        warning_in=IrsAuthorizationWarningCreate(
            authorization_id=authorization.id,
            threshold_days=threshold_days,
            sent_at=datetime.now(timezone.utc),
        ),
        firm_id=authorization.firm_id,
    )
    log_event(
        firm_id=authorization.firm_id,
        event_type="irs_authorization.expiry_warning_sent",
        entity_type="irs_authorization",
        entity_id=authorization.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "days_until_expiry": (
                (authorization.valid_until - as_of).days
                if authorization.valid_until else None
            ),
            "warning_tier": threshold_days,
        }
    )


def check_expiring_authorizations() -> dict:
    """
    Scheduler function: warn on active authorizations approaching expiry and
    close out any that have already lapsed.
    Creates its own DB session. Safe to call from background tasks.

    The tier ladder and direct delivery arrive in Phase A3. This phase wires
    the two queries and makes the lapsed branch reachable, which it was not
    while a single window query filtered out everything already past due.
    """
    from app.db.session import SessionLocal
    from app.services.event_bus import emit_event_sync
    from app.core.enums import TriggerEvent

    db = SessionLocal()
    try:
        # Computed ONCE and passed to both queries. If the two ran against
        # different dates, an authorization expiring on the boundary would
        # fall into neither set and be skipped silently. Correctness lives
        # here, not in the schedule: this must be right at 4am too.
        cutoff = crud_auth.compute_expiry_cutoff_date()

        expiring = crud_auth.get_authorizations_in_warning_window(
            db, max_days=60, as_of=cutoff
        )
        alerts_emitted = 0

        for auth in expiring:
            # One bad row must never silence every row after it. A nightly
            # compliance job that aborts halfway is the failure this whole
            # phase exists to prevent.
            try:
                days_remaining = (auth.valid_until - cutoff).days

                # Kept so nothing downstream breaks. Delivery no longer
                # depends on it.
                emit_event_sync(
                    event=TriggerEvent.irs_authorization_expiry_approaching,
                    payload={
                        "firm_id": str(auth.firm_id),
                        "client_id": str(auth.client_id),
                        "authorization_id": str(auth.id),
                        "form_type": auth.form_type,
                        "valid_until": auth.valid_until.isoformat(),
                        "days_remaining": days_remaining,
                    },
                )

                applicable = [t for t in WARNING_TIERS if days_remaining <= t]
                if not applicable:
                    continue

                most_urgent = min(applicable)

                # Less urgent tiers are deliberately not backfilled. Because
                # days_remaining only ever decreases, a tier that never fired
                # can never become most_urgent again, so stamping it would
                # only put a false sent_at in the table. An authorization
                # created 10 days before expiry shows rows for 30, 7 and 0
                # and none for 60, which is exactly what happened.
                already_sent = crud_warning.get_warning_for_threshold(
                    db=db,
                    firm_id=auth.firm_id,
                    authorization_id=auth.id,
                    threshold_days=most_urgent,
                )
                if already_sent is not None:
                    continue

                # Row written only after the send succeeds. If the process
                # dies mid-sweep, a duplicate warning tomorrow is a minor
                # annoyance; a silently skipped warning is not.
                if _deliver_expiry_warning(db=db, authorization=auth, as_of=cutoff):
                    _record_warning_sent(
                        db=db,
                        authorization=auth,
                        threshold_days=most_urgent,
                        as_of=cutoff,
                    )
                    alerts_emitted += 1
            except Exception:
                logger.exception(
                    "IRS expiry warning failed for authorization %s (firm %s)",
                    auth.id, auth.firm_id,
                )
                db.rollback()

        # Separate pass. Catches anything that lapsed without being closed
        # out, however long ago. Writing status = "expired" drains this set.
        lapsed = crud_auth.get_lapsed_active_authorizations(db, as_of=cutoff)
        expired_count = 0
        for auth in lapsed:
            try:
                # Fire tier 0 if it never went out. An authorization that
                # lapsed before this feature existed gets one final notice
                # rather than expiring silently.
                already_sent = crud_warning.get_warning_for_threshold(
                    db=db,
                    firm_id=auth.firm_id,
                    authorization_id=auth.id,
                    threshold_days=0,
                )
                if already_sent is None:
                    if _deliver_expiry_warning(db=db, authorization=auth, as_of=cutoff):
                        _record_warning_sent(
                            db=db,
                            authorization=auth,
                            threshold_days=0,
                            as_of=cutoff,
                        )
                        alerts_emitted += 1

                mark_authorization_expired(
                    db=db,
                    authorization=auth,
                    firm_id=auth.firm_id,
                )
                expired_count += 1
            except Exception:
                logger.exception(
                    "IRS expiry close-out failed for authorization %s (firm %s)",
                    auth.id, auth.firm_id,
                )
                db.rollback()

        return {
            "checked": len(expiring),
            "alerts_emitted": alerts_emitted,
            "expired": expired_count,
        }
    finally:
        db.close()


def update_authorization(
    *,
    db: Session,
    authorization,
    firm_id: UUID,
    auth_in: IrsAuthorizationUpdate,
):
    """
    Update an authorization, resetting its warning ladder when the expiry
    date moves.

    A changed valid_until makes every tier already recorded meaningless,
    because those tiers were computed against the old date. Clearing the
    rows lets the ladder recompute from scratch on the next sweep.

    This is the one and only trigger for deleting warning rows. Supersession
    does not clear them, expiry does not clear them, and revocation does not
    clear them, because in all three cases the history is the record of what
    the system did before the outcome.

    Renewals, corrections, and plain typos all resolve through this single
    mechanism. A mistyped year that gets fixed recomputes the ladder, which
    is why no separate status value is needed for "entered wrong".
    """
    changes = auth_in.model_dump(exclude_unset=True)

    # Only a real change resets the ladder. Rewriting valid_until to the
    # value it already holds is not a change and must not discard history.
    valid_until_changing = (
        "valid_until" in changes
        and changes["valid_until"] != authorization.valid_until
    )

    if valid_until_changing:
        cleared = crud_warning.delete_warnings_for_authorization(
            db=db,
            firm_id=firm_id,
            authorization_id=authorization.id,
        )
        log_event(
            firm_id=firm_id,
            event_type="irs_authorization.warning_ladder_reset",
            entity_type="irs_authorization",
            entity_id=authorization.id,
            actor_type="staff",
            actor_id=None,
            metadata={
                "previous_valid_until": (
                    authorization.valid_until.isoformat()
                    if authorization.valid_until else None
                ),
                "new_valid_until": (
                    changes["valid_until"].isoformat()
                    if changes["valid_until"] else None
                ),
                "warnings_cleared": cleared,
            }
        )

    return crud_auth.update_irs_authorization(
        db=db,
        auth=authorization,
        auth_in=auth_in,
    )


def mark_authorization_renewed(
    *,
    db: Session,
    authorization,
    firm_id,
    actor_id=None,
) -> None:
    log_event(
        firm_id=firm_id,
        event_type="irs_authorization.renewed",
        entity_type="irs_authorization",
        entity_id=authorization.id,
        actor_type="system",
        actor_id=actor_id,
        metadata={
            "form_type": str(authorization.form_type) if hasattr(authorization, "form_type") and authorization.form_type else None,
            "new_expiry_date": authorization.valid_until.isoformat() if hasattr(authorization, "valid_until") and authorization.valid_until else None,
            "client_id": str(authorization.client_id) if hasattr(authorization, "client_id") else None,
        }
    )


def mark_authorization_expired(
    *,
    db: Session,
    authorization,
    firm_id,
) -> None:
    """
    Close out an authorization that lapsed on its own.

    Writes status = "expired" as real control state rather than only logging.
    That gate always existed and was decorative while nothing ever wrote the
    status. Do not add a bypass.

    Since Phase F1 Step 8 this write no longer decides the gate. The gate
    reads resolve_authorization_state, which judges valid_until against the
    same cutoff this sweep uses, so the row is already refused from the
    moment it lapses rather than from the moment this runs. What this write
    still owns is the row's own status, and it is the only thing that may
    write it.

    Warning rows are NOT deleted here. The ladder history is what the
    expiry event reports on, and it stays on the row afterwards.
    """
    warnings = crud_warning.list_warnings_for_authorization(
        db=db,
        firm_id=firm_id,
        authorization_id=authorization.id,
    )

    # list_warnings_for_authorization orders by sent_at descending, so the
    # first row is the most recent warning this authorization received.
    #
    # Both sides of this subtraction are UTC on purpose. sent_at is a
    # timezone-aware UTC timestamp, so pairing it with date.today(), which is
    # the server's LOCAL date, mixes two calendars and comes out one day off
    # whenever the server's local date and its UTC date disagree.
    days_since_expiry_warning = None
    if warnings:
        today_utc = datetime.now(timezone.utc).date()
        days_since_expiry_warning = (today_utc - warnings[0].sent_at.date()).days

    authorization.status = "expired"
    db.commit()

    log_event(
        firm_id=firm_id,
        event_type="irs_authorization.expired",
        entity_type="irs_authorization",
        entity_id=authorization.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "form_type": str(authorization.form_type) if hasattr(authorization, "form_type") and authorization.form_type else None,
            "expired_date": authorization.valid_until.isoformat() if hasattr(authorization, "valid_until") and authorization.valid_until else None,
            "client_id": str(authorization.client_id) if hasattr(authorization, "client_id") else None,
            "warning_tiers_fired": len(warnings),
            "days_since_expiry_warning": days_since_expiry_warning,
        }
    )


def _supersede_prior_active_authorizations(
    *,
    db: Session,
    firm_id: UUID,
    client_id: UUID,
    form_type: str,
    replacement_id: UUID,
) -> int:
    """
    Retire any authorization this one replaces, and return how many.

    Scoped to firm AND client AND form_type. This is deliberately NOT "one
    active authorization per client": a client can hold an 8821 and a 2848
    at the same time, and resolution runs once per form type, so retiring the
    2848 because an 8821 activated would break transcript access outright.

    Superseded rows are never deleted. They keep their signed_document_id,
    so the attached document stays where it is in the Documents module, and
    they keep their full warning history, which is the renewal lead time
    signal. transcript_requests.irs_authorization_id is ondelete="RESTRICT"
    so the database would refuse a delete regardless.
    """
    from app.models.irs_authorization import IrsAuthorization

    priors = db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.firm_id == firm_id,
            IrsAuthorization.client_id == client_id,
            IrsAuthorization.form_type == form_type,
            IrsAuthorization.status == "active",
            IrsAuthorization.id != replacement_id,
        )
    ).scalars().all()

    if not priors:
        return 0

    today = date.today()
    for prior in priors:
        days_remaining = None
        if prior.valid_until is not None:
            days_remaining = (prior.valid_until - today).days

        warnings = crud_warning.list_warnings_for_authorization(
            db=db,
            firm_id=firm_id,
            authorization_id=prior.id,
        )

        # No commit here on purpose. The caller sets the replacement to
        # "active" and commits once, so both status writes land in a single
        # transaction. Committing separately would allow a failure between
        # the two to leave the prior authorization superseded and the
        # replacement still pending_signature, which is no active
        # authorization at all. Nothing would warn about it either, since
        # both sweep queries filter status == "active".
        prior.status = "superseded"

        # Days remaining paired with tiers fired is the renewal lead time
        # signal: how much room was left, and how hard the system had
        # already pushed, at the moment the firm actually renewed.
        log_event(
            firm_id=firm_id,
            event_type="irs_authorization.superseded",
            entity_type="irs_authorization",
            entity_id=prior.id,
            actor_type="system",
            actor_id=None,
            metadata={
                "superseded_authorization_id": str(prior.id),
                "new_authorization_id": str(replacement_id),
                "form_type": str(prior.form_type) if prior.form_type else None,
                "client_id": str(client_id),
                "days_remaining_at_supersession": days_remaining,
                "warning_tiers_fired": len(warnings),
            }
        )

    return len(priors)


def activate_authorization_for_envelope(
    *,
    db: Session,
    envelope_id: UUID,
    firm_id: UUID,
) -> None:
    """
    Called when a signature envelope is signed. If that envelope is an IRS
    authorization form, flip the linked IrsAuthorization from
    pending_signature to active and fire the behavioral event. No-op if the
    envelope is not linked to an authorization (the common case for plain
    engagement letters).
    """
    from app.models.irs_authorization import IrsAuthorization

    auth = db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.signature_envelope_id == envelope_id,
            IrsAuthorization.firm_id == firm_id,
        )
    ).scalar_one_or_none()

    if auth is None:
        return

    old_status = auth.status
    if old_status != "pending_signature":
        return

    _supersede_prior_active_authorizations(
        db=db,
        firm_id=firm_id,
        client_id=auth.client_id,
        form_type=auth.form_type,
        replacement_id=auth.id,
    )

    auth.status = "active"
    if auth.valid_from is None:
        auth.valid_from = date.today()
    db.commit()

    log_event(
        firm_id=firm_id,
        event_type="irs_authorization.activated",
        entity_type="irs_authorization",
        entity_id=auth.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "from_status": old_status,
            "to_status": "active",
            "form_type": str(auth.form_type) if auth.form_type else None,
            "client_id": str(auth.client_id),
            "valid_until": auth.valid_until.isoformat() if auth.valid_until else None,
        }
    )
