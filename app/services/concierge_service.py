# app/services/concierge_service.py

import re
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

# Matches two consecutive title-cased words immediately followed by a number,
# e.g. "Sarah Mitchell 12" or "James Okafor 47", a heuristic for invented
# identities paired with specific counts on the plain conversational path.
_FABRICATED_IDENTITY_RE = re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\s+\d+')


def _detect_possible_fabrication(
    *,
    response_text: str,
    on_tool_path: bool,
    tool_executed: bool,
    is_low_confidence: bool,
) -> bool:
    # If the existing hedge detector already caught this, this flag adds nothing new.
    if is_low_confidence:
        return False

    # Reliable form: tool-use path entered but no tool actually ran, yet the
    # model returned a substantive answer. This is the pattern that produced
    # the invented staff member tonight.
    if on_tool_path and not tool_executed and len(response_text) > 80:
        return True

    # Heuristic form: plain conversational path with patterns suggestive of
    # fabricated specific firm data. Conservative -- only flag when multiple
    # signals appear together to avoid false positives on legitimate answers.
    if not on_tool_path:
        has_dollar = '$' in response_text
        has_percent = '%' in response_text
        has_identity_with_number = bool(_FABRICATED_IDENTITY_RE.search(response_text))
        if has_identity_with_number or (has_dollar and has_percent):
            return True

    return False


def log_question_asked(
    *,
    db,
    firm_id,
    current_user_id,
    last_user_text,
    full_response,
    entity_type,
    on_tool_path: bool = False,
    tool_executed: bool = False,
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
        is_possible_fabrication = _detect_possible_fabrication(
            response_text=response_text,
            on_tool_path=on_tool_path,
            tool_executed=tool_executed,
            is_low_confidence=is_low_confidence,
        )

        log_entry = ConciergeQuestionLog(
            firm_id=firm_id,
            question_text=last_user_text[:2000],
            response_summary=response_text[:500],
            low_confidence=is_low_confidence,
            possible_fabrication=is_possible_fabrication,
        )
        db.add(log_entry)
        db.commit()

        metadata = {
            "question": last_user_text[:500],
            "low_confidence": is_low_confidence,
            "possible_fabrication": is_possible_fabrication,
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
