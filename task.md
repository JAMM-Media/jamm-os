# JAMM PX — Behavioral Event Log: Complete Coverage Pass

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Backend only. No frontend changes.
- Always fire-and-forget — never let log_event failures surface to the user.
- Import `log_event` from `app.services.behavioral_log` at the top of each file if not already imported.
- No migrations needed — the behavioral_events table already exists.

---

## TASK 1 — Fee schedule delta: log old and new values

**File to edit:** `app/api/users.py`

The existing `firm.fee_schedule_updated` event only logs the new fee schedule. Update it to also capture the previous values so the Index can track rate changes over time.

Find the existing fee schedule log_event block and replace the metadata:

```python
if "fee_schedule" in payload:
    from app.services.behavioral_log import log_event
    previous_schedule = (firm.settings or {}).get("fee_schedule", {})
    log_event(
        firm_id=current_firm.id,
        event_type="firm.fee_schedule_updated",
        entity_type="firm",
        entity_id=current_firm.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "fee_schedule": payload["fee_schedule"],
            "previous_fee_schedule": previous_schedule,
            "count": len(payload["fee_schedule"]),
            "changed_types": [
                k for k in payload["fee_schedule"]
                if str(payload["fee_schedule"].get(k)) != str(previous_schedule.get(k))
            ],
        }
    )
```

Note: capture `previous_schedule` BEFORE calling `crud_firm.update_firm` — it must be read from the current firm state before the update overwrites it. Move the `if "fee_schedule"` block to run before `crud_firm.update_firm`, capture the previous value, then run the update, then log.

---

## TASK 2 — Portal first login detection

**File to edit:** `app/services/portal_auth_service.py` (or wherever `portal.login` is logged — search for `event_type="portal.login"`)

The portal login event fires on every login. Add a `portal.first_login` event that fires only when it's the client's first ever portal login.

The Client model has `portal_last_login_at`. If this field is null before the login, it's the first login.

Find both `portal.login` log_event calls (there are two — one for magic link, one for password). In both, add a first_login check immediately before or after the existing `portal.login` log_event:

```python
# Detect first login
if client.portal_last_login_at is None:
    log_event(
        firm_id=client.firm_id,
        event_type="portal.first_login",
        entity_type="client",
        entity_id=client.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "time_since_invitation_days": (
                (datetime.now(timezone.utc) - client.portal_invited_at).days
                if hasattr(client, 'portal_invited_at') and client.portal_invited_at
                else None
            ),
            "login_method": "magic_link",  # or "password" depending on which handler
        }
    )
```

Use `"magic_link"` or `"password"` as appropriate for each handler.

---

## TASK 3 — Portal activity events

**File to edit:** `app/api/portal.py`

Add log_event calls to these portal endpoints. Check if `log_event` is already imported — if not add it.

### 3A — portal.message_sent

In `portal_send_message`, after the return value is computed (the message is sent), add:

```python
log_event(
    firm_id=current_client.firm_id,
    event_type="portal.message_sent",
    entity_type="client",
    entity_id=current_client.id,
    actor_type="client",
    actor_id=None,
    metadata={
        "time_of_day": datetime.now(timezone.utc).hour,
        "day_of_week": datetime.now(timezone.utc).weekday(),
    }
)
```

Note: `portal_send_message` currently does `return msg_service.send_message_client(...)` in one line. Capture the return value first, log, then return it.

### 3B — portal.invoice_viewed

In `portal_get_invoice` (the GET single invoice endpoint), after the invoice is fetched successfully, add:

```python
log_event(
    firm_id=current_client.firm_id,
    event_type="portal.invoice_viewed",
    entity_type="invoice",
    entity_id=invoice_id,
    actor_type="client",
    actor_id=None,
    metadata={
        "invoice_amount": float(invoice.total_amount) if hasattr(invoice, 'total_amount') else None,
        "invoice_status": str(invoice.status) if hasattr(invoice, 'status') else None,
        "days_since_sent": (
            (datetime.now(timezone.utc) - invoice.sent_at).days
            if hasattr(invoice, 'sent_at') and invoice.sent_at
            else None
        ),
    }
)
```

### 3C — portal.invoice_paid

In `portal_pay_invoice`, after a successful payment (after Stripe confirms, not just on attempt), add:

```python
log_event(
    firm_id=current_client.firm_id,
    event_type="portal.invoice_paid",
    entity_type="invoice",
    entity_id=invoice_id,
    actor_type="client",
    actor_id=None,
    metadata={
        "payment_method": "stripe",
        "time_of_day": datetime.now(timezone.utc).hour,
    }
)
```

### 3D — portal.document_uploaded

Find where clients upload documents through the portal. Add:

```python
log_event(
    firm_id=current_client.firm_id,
    event_type="portal.document_uploaded",
    entity_type="client",
    entity_id=current_client.id,
    actor_type="client",
    actor_id=None,
    metadata={
        "time_of_day": datetime.now(timezone.utc).hour,
        "day_of_week": datetime.now(timezone.utc).weekday(),
    }
)
```

---

## TASK 4 — Automation toggle events

**File to edit:** `app/api/automation_rules.py`

The automation.fired and automation.failed events are already logged. But there's no event when a firm enables or disables a rule. This is critical for the Index — automation adoption sequence (which rules do firms enable first, and in what order) is one of the strongest predictors of engagement.

In `toggle_rule`, after `crud_rule.toggle_rule(...)`, add:

```python
from app.services.behavioral_log import log_event

result = crud_rule.toggle_rule(db, rule=rule, enabled=enabled)

log_event(
    firm_id=current_firm.id,
    event_type="firm.automation_enabled" if enabled else "firm.automation_disabled",
    entity_type="automation_rule",
    entity_id=rule_id,
    actor_type="staff",
    actor_id=None,
    metadata={
        "rule_name": rule.name,
        "rule_type": rule.trigger_event if hasattr(rule, 'trigger_event') else None,
        "execution_count": rule.execution_count if hasattr(rule, 'execution_count') else None,
    }
)

return result
```

Replace the existing `return crud_rule.toggle_rule(...)` with this block.

---

## TASK 5 — Invoice overdue event

**File to edit:** `app/services/invoice_service.py` or wherever invoice status is set to overdue (search for `invoice.overdue` or `InvoiceStatus.overdue`)

Add an event when an invoice first becomes overdue:

```python
log_event(
    firm_id=invoice.firm_id,
    event_type="invoice.overdue",
    entity_type="invoice",
    entity_id=invoice.id,
    actor_type="system",
    actor_id=None,
    metadata={
        "amount": float(invoice.total_amount) if hasattr(invoice, 'total_amount') else None,
        "days_since_sent": (
            (datetime.now(timezone.utc) - invoice.sent_at).days
            if hasattr(invoice, 'sent_at') and invoice.sent_at
            else None
        ),
        "client_id": str(invoice.client_id),
    }
)
```

---

## TASK 6 — Document signed event

**File to edit:** `app/api/esign.py` — in the webhook handler where signature completion is processed

When Dropbox Sign calls the webhook confirming a document was signed, add:

```python
log_event(
    firm_id=envelope.firm_id,
    event_type="engagement_letter.signed",
    entity_type="signature_envelope",
    entity_id=envelope.id,
    actor_type="client",
    actor_id=None,
    metadata={
        "client_id": str(envelope.client_id),
        "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
        "days_to_sign": (
            (datetime.now(timezone.utc) - envelope.sent_at).days
            if hasattr(envelope, 'sent_at') and envelope.sent_at
            else None
        ),
    }
)
```

Find where the webhook updates the envelope status to "signed" or "completed" and add this immediately after.

---

## TASK 7 — Template usage at send time: enrich existing prepare event

**File to edit:** `app/api/esign.py`

The `engagement_letter.prepared` event already exists. Enrich its metadata with the template's engagement_type so we can track which templates get used most:

Find the existing `engagement_letter.prepared` log_event and update its metadata:

```python
metadata={
    "client_id": str(client.id),
    "engagement_id": str(payload.engagement_id),
    "template_id": str(payload.template_id),
    "template_name": template.name,
    "template_engagement_type": template.engagement_type,
    "fee_amount": payload.fee_amount or None,
    "engagement_type": getattr(engagement, "engagement_type", None),
}
```

---

## EXECUTION ORDER

1. Task 1 — users.py (fee schedule delta)
2. Task 2 — portal_auth_service.py (first login)
3. Task 3 — portal.py (portal activity events)
4. Task 4 — automation_rules.py (toggle events)
5. Task 5 — invoice_service.py (overdue event)
6. Task 6 — esign.py webhook (signed event)
7. Task 7 — esign.py prepare (enrich metadata)

No frontend changes. No migrations needed.
After all tasks: report every file modified.