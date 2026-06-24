# app/services/esign_reminder_service.py

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.crud import signature_envelope as crud_envelope
from app.db.session import SessionLocal
from app.models.automation_rule import AutomationRule
from app.models.firm import Firm
from app.models.signature_envelope import SignatureEnvelope
from app.schemas.signature_envelope import SignatureEnvelopeUpdate
from app.services import dropbox_sign
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)


def run_esign_auto_reminders() -> None:
    try:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            rules = db.execute(
                select(AutomationRule).where(
                    AutomationRule.name == "E-Signature Reminder (2-day)",
                    AutomationRule.is_enabled == True,  # noqa: E712
                )
            ).scalars().all()

            for rule in rules:
                firm = db.execute(
                    select(Firm).where(Firm.id == rule.firm_id)
                ).scalars().first()
                if not firm:
                    continue

                first_days = int(
                    (firm.settings or {}).get('esign_first_reminder_days', 2)
                )
                cutoff = now - timedelta(days=first_days)

                envelopes = db.execute(
                    select(SignatureEnvelope).where(
                        SignatureEnvelope.firm_id == rule.firm_id,
                        SignatureEnvelope.status == 'sent',
                        SignatureEnvelope.auto_reminder_sent_at.is_(None),
                        SignatureEnvelope.sent_at <= cutoff,
                    )
                ).scalars().all()

                for envelope in envelopes:
                    try:
                        signer_email = (
                            envelope.signers[0]['email']
                            if envelope.signers
                            else None
                        )
                        dropbox_sign.send_reminder(
                            signature_request_id=envelope.provider_envelope_id,
                            signer_email=signer_email,
                        )
                        crud_envelope.update_signature_envelope(
                            db,
                            envelope,
                            SignatureEnvelopeUpdate(
                                auto_reminder_sent_at=now,
                                last_reminder_sent_at=now,
                                reminder_count=(envelope.reminder_count or 0) + 1,
                            ),
                        )
                        write_audit_log(
                            db=db,
                            firm_id=envelope.firm_id,
                            action='esign.auto_reminder_sent',
                            actor_type='system',
                            entity_type='signature_envelope',
                            entity_id=envelope.id,
                        )
                        log_event(
                            firm_id=envelope.firm_id,
                            event_type='esign.reminder_sent',
                            entity_type='signature_envelope',
                            entity_id=envelope.id,
                            actor_type='system',
                            actor_id=None,
                            metadata={
                                'auto': True,
                                'reminder_number': 1,
                                'client_id': str(envelope.client_id),
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            "Auto reminder failed for envelope %s: %s",
                            envelope.id, exc, exc_info=True,
                        )
        finally:
            db.close()
    except Exception as exc:
        logger.error("run_esign_auto_reminders failed: %s", exc, exc_info=True)


def run_esign_escalation_check() -> None:
    try:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            firms = db.execute(
                select(Firm).where(Firm.is_active == True)  # noqa: E712
            ).scalars().all()

            for firm in firms:
                escalation_days = int(
                    (firm.settings or {}).get('esign_escalation_days', 3)
                )
                cutoff = now - timedelta(days=escalation_days)

                envelopes = db.execute(
                    select(SignatureEnvelope).where(
                        SignatureEnvelope.firm_id == firm.id,
                        SignatureEnvelope.status == 'sent',
                        SignatureEnvelope.escalated_at.is_(None),
                        SignatureEnvelope.reminder_count >= 2,
                        SignatureEnvelope.last_reminder_sent_at <= cutoff,
                    )
                ).scalars().all()

                for envelope in envelopes:
                    try:
                        sent_at = envelope.sent_at
                        if sent_at is not None and sent_at.tzinfo is None:
                            sent_at = sent_at.replace(tzinfo=timezone.utc)
                        days_waiting = (now - sent_at).days if sent_at else 0

                        crud_envelope.update_signature_envelope(
                            db,
                            envelope,
                            SignatureEnvelopeUpdate(escalated_at=now),
                        )
                        log_event(
                            firm_id=envelope.firm_id,
                            event_type='esign.escalated',
                            entity_type='signature_envelope',
                            entity_id=envelope.id,
                            actor_type='system',
                            actor_id=None,
                            metadata={
                                'days_waiting': days_waiting,
                                'client_id': str(envelope.client_id),
                                'reminder_count': envelope.reminder_count,
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            "Escalation check failed for envelope %s: %s",
                            envelope.id, exc, exc_info=True,
                        )
        finally:
            db.close()
    except Exception as exc:
        logger.error("run_esign_escalation_check failed: %s", exc, exc_info=True)
