# Phase 0 · Step 1 — Scope Decision

**Date:** 2025-10-15

## Choose ONE launch scope
- [ ] Tiny MVP (backend-only): Clients, Tasks/Workflows, Email reminders, JWT auth, Postgres, basic admin UI.
- [x] MVP (recommended): + Google Calendar (one-way), File uploads (S3), E‑signature (single template), Invoicing + Stripe.
- [ ] Premium v1 (later): 2‑way calendar sync, QuickBooks integration, AI features, audit dashboards, white-labeling.

### Why we chose this
Write 2–3 sentences about why the selected scope matches your skill and timeline.

### Non-goals (explicitly out of scope for MVP)
- 2‑way calendar sync
- QuickBooks (full) bi‑directional sync
- SOC2/ISO certification (design-ready, not audited)
- AI OCR & RAG search
- White‑labeling/multi-tenant theming

## MVP Feature Checklist
- [ ] Auth (JWT), RBAC (admin/staff/client)
- [ ] Clients/Engagements CRUD
- [ ] Tasks/Workflows + statuses
- [ ] Email reminders (SendGrid sandbox)
- [ ] Google Calendar one‑way push
- [ ] File upload/download via presigned URLs
- [ ] E‑signature flow for engagement letters
- [ ] Invoices + Stripe checkout + webhook
- [ ] Basic admin or client portal with 4 pages

## Success Criteria (Definition of "good enough" to launch)
- 3 external testers complete a full workflow end‑to‑end without your help
- < 2 P1 bugs during a week of use
- Time-to-onboard new client < 10 minutes
- First paid invoice processed successfully
