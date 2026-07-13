# app/services/ack_parser_service.py

import re

from sqlalchemy.orm import Session

from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event


def parse_ack_file(contents: str) -> list[dict]:
    """
    Parse a .ack file and return structured records.
    Never touches the database. Tax IDs are returned only for
    use as lookup keys — callers must discard them after lookup.
    """
    lines = [line.strip() for line in contents.splitlines()]
    non_blank = [l for l in lines if l]

    if not non_blank:
        raise ValueError("ACK file is empty or contains no readable lines.")

    pipe_lines = [l for l in non_blank if "|" in l]
    use_pipe = len(pipe_lines) >= len(non_blank) // 2

    records = []

    if use_pipe:
        for line in non_blank:
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            # Accept lines that start with ACK or any record type indicator,
            # and lines where the second field looks like a 9-digit tax ID.
            taxpayer_id = parts[1] if len(parts) > 1 else ""
            if not re.match(r"^\d{9}$", taxpayer_id):
                continue
            records.append({
                "taxpayer_id": parts[1],
                "confirmation_number": parts[2],
                "form_type": parts[3],
                "status": parts[4].upper(),
                "tax_year": parts[5] if len(parts) > 5 else None,
            })
    else:
        for line in non_blank:
            taxpayer_id = _extract_kv(line, r"TaxpayerID=(\S+)")
            confirmation_number = _extract_kv(line, r"ConfirmationNum=(\S+)")
            form_type = _extract_kv(line, r"FormType=(\S+)")
            status = _extract_kv(line, r"Status=(\S+)")
            tax_year = _extract_kv(line, r"TaxYear=(\S+)")

            if not taxpayer_id or not re.match(r"^\d{9}$", taxpayer_id):
                continue
            if not confirmation_number or not form_type or not status:
                continue
            records.append({
                "taxpayer_id": taxpayer_id,
                "confirmation_number": confirmation_number,
                "form_type": form_type,
                "status": status.upper(),
                "tax_year": tax_year,
            })

    if not records:
        raise ValueError(
            "No valid ACK records found in file. "
            "Expected pipe-delimited lines (ACK|TaxID|ConfNum|FormType|Status) "
            "or key=value lines (TaxpayerID=... ConfirmationNum=... FormType=... Status=...)."
        )

    return records


def _extract_kv(line: str, pattern: str) -> str | None:
    m = re.search(pattern, line)
    return m.group(1) if m else None


def record_efiled(
    *,
    db: Session,
    firm_id,
    engagement_id,
    actor_id,
    confirmation_number,
    form_type,
    status,
    tax_year,
) -> None:
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="engagement.efiled",
        actor_id=actor_id,
        actor_type="staff",
        entity_type="engagement",
        entity_id=engagement_id,
        metadata={
            "confirmation_number": confirmation_number,
            "form_type": form_type,
            "irs_status": status,
        },
    )

    log_event(
        event_type="engagement.efiled",
        firm_id=firm_id,
        entity_type="engagement",
        entity_id=engagement_id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "confirmation_number": confirmation_number,
            "form_type": form_type,
            "status": status,
            "tax_year": tax_year,
        },
    )
