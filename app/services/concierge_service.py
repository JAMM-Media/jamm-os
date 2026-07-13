# app/services/concierge_service.py

from app.models.concierge_question_log import ConciergeQuestionLog
from app.services.behavioral_log import log_event

LOW_CONFIDENCE_PHRASES = [
    "i'm not sure",
    "i don't have information",
    "i don't know",
    "i cannot confirm",
    "i'm unable to",
    "i am not sure",
    "i am unable to",
    "i don't have access",
    "i cannot find",
    "not available in my",
]


def log_question_asked(
    *,
    db,
    firm_id,
    current_user_id,
    last_user_text,
    full_response,
    entity_type,
    extra_metadata=None,
):
    try:
        response_text = "\n".join(
            line[6:] for line in full_response.split("\n")
            if line.startswith("data:") and not line.startswith("data: [FILTERED]")
        ).strip()
        if not response_text:
            return

        is_low_confidence = any(p in response_text.lower() for p in LOW_CONFIDENCE_PHRASES)

        log_entry = ConciergeQuestionLog(
            firm_id=firm_id,
            question_text=last_user_text[:2000],
            response_summary=response_text[:500],
            low_confidence=is_low_confidence,
        )
        db.add(log_entry)
        db.commit()

        metadata = {
            "question": last_user_text[:500],
            "low_confidence": is_low_confidence,
            "response_length": len(response_text),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        log_event(
            firm_id=firm_id,
            event_type="concierge.question_asked",
            actor_type="user",
            actor_id=current_user_id,
            entity_type=entity_type,
            metadata=metadata,
        )
    except Exception:
        pass  # non-fatal -- logging failure must never block the response
