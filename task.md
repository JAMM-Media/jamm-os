# JAMM PX — Behavioral Event Log: Wire Missing Events

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Backend only. No frontend changes.
- Follow the exact existing `log_event` call pattern — fire-and-forget, never block the main operation.
- Import `log_event` from `app.services.behavioral_log` at the top of each file if not already imported.
- Never add `log_event` inside a try/except that would surface its failure to the user.

---

## TASK 1 — Wire behavioral events for e-signature flow

**File to edit:** `app/api/esign.py`

Add `log_event` calls for the three key esign events. Check if `log_event` is already imported — if not, add:
```python
from app.services.behavioral_log import log_event
```

### 1A — engagement_letter.sent (after successful send_envelope)

In the `send_envelope` endpoint, after `updated = crud_envelope.update_signature_envelope(...)` and the existing `write_audit_log` call, add:

```python
log_event(
    firm_id=current_firm.id,
    event_type="engagement_letter.sent",
    entity_type="signature_envelope",
    entity_id=envelope_id,
    actor_type="staff",
    actor_id=current_user.id if hasattr(current_user, 'id') else None,
    metadata={
        "client_id": str(envelope.client_id),
        "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
        "provider": envelope.provider,
    }
)
```

Note: `send_envelope` uses `_: User = Depends(require_manager_or_above)` so the current user isn't directly available. Add `current_user: User = Depends(get_current_user)` as a parameter to `send_envelope`. Check existing imports for `get_current_user`.

### 1B — engagement_letter.prepared (after prepare_letter creates the envelope)

In the `prepare_letter` endpoint, after `return crud_envelope.create_signature_envelope(...)`, capture the return value and add the log event:

```python
envelope = crud_envelope.create_signature_envelope(db, envelope_schema, firm_id=current_firm.id)

log_event(
    firm_id=current_firm.id,
    event_type="engagement_letter.prepared",
    entity_type="signature_envelope",
    entity_id=envelope.id,
    actor_type="staff",
    actor_id=current_user.id,
    metadata={
        "client_id": str(client.id),
        "engagement_id": str(payload.engagement_id),
        "template_id": str(payload.template_id),
        "fee_amount": payload.fee_amount or None,
    }
)

return envelope
```

### 1C — engagement_letter.uploaded (in upload_and_prepare)

In `upload_and_prepare`, the `write_audit_log` call is already there. Add a `log_event` call immediately after it:

```python
log_event(
    firm_id=current_firm.id,
    event_type="engagement_letter.uploaded",
    entity_type="signature_envelope",
    entity_id=envelope.id,
    actor_type="staff",
    actor_id=current_user.id,
    metadata={
        "client_id": str(client.id),
        "engagement_id": str(engagement_id),
        "filename": file.filename or "engagement_letter.pdf",
        "size_bytes": len(pdf_bytes),
    }
)
```

---

## TASK 2 — Wire behavioral event for fee schedule updates

**File to edit:** `app/api/users.py`

In the `update_my_firm_settings` endpoint, after the `updated = crud_firm.update_firm(...)` call, add a log event if the payload contains `fee_schedule`:

```python
if "fee_schedule" in payload:
    from app.services.behavioral_log import log_event
    log_event(
        firm_id=current_firm.id,
        event_type="firm.fee_schedule_updated",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "fee_schedule": payload["fee_schedule"],
            "count": len(payload["fee_schedule"]),
        }
    )

return updated
```

Note: we don't log the actual fee amounts in metadata — only which engagement types were set and how many. The fee amounts themselves are stored in `firm.settings.fee_schedule` and queried directly for benchmarking. This protects against logging sensitive pricing data in the event stream.

---

## TASK 3 — Wire behavioral event for letter template operations

**File to edit:** `app/api/esign.py`

Add log events for template create and update — these track which firms are actively managing their templates, which feeds template adoption metrics.

### 3A — In `create_letter_template`, after the return:

```python
template = crud_template.create_template(db, payload, firm_id=current_firm.id)

log_event(
    firm_id=current_firm.id,
    event_type="letter_template.created",
    entity_type="letter_template",
    entity_id=template.id,
    actor_type="staff",
    actor_id=current_user.id if hasattr(current_user, 'id') else None,
    metadata={
        "engagement_type": payload.engagement_type,
        "variable_count": len(payload.variable_fields),
    }
)

return template
```

Add `current_user: User = Depends(get_current_user)` to `create_letter_template` parameters if not already there. The endpoint currently uses `_: User = Depends(require_staff_or_above)` — replace `_` with `current_user` and change the dependency to `get_current_user`, then add a separate `_: object = Depends(require_staff_or_above)` to keep the role check. Or simply keep `_` and pass `actor_id=None` for simplicity.

For simplicity: just pass `actor_id=None` and don't change the endpoint signature.

### 3B — In `update_letter_template`, after the return:

```python
updated = crud_template.update_template(db, template, payload)

log_event(
    firm_id=current_firm.id,
    event_type="letter_template.updated",
    entity_type="letter_template",
    entity_id=template_id,
    actor_type="staff",
    actor_id=None,
    metadata={
        "engagement_type": payload.engagement_type,
    }
)

return updated
```

---

## EXECUTION ORDER

1. Task 1 — app/api/esign.py (esign events)
2. Task 2 — app/api/users.py (fee schedule event)
3. Task 3 — app/api/esign.py (template events, same file as Task 1)

No migrations needed — the `behavioral_events` table already exists.
No frontend changes needed.
After all tasks: report every file modified.