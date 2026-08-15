<!-- Created 2026-08-14/15 during a live build session. Updated 2026-08-15 to reflect the completed backend booking sequence and two real bugs found and handled during the session. This document captures the full reasoning behind every item on the priority list, not just the item itself, so context is never lost to a closed chat window. -->

# CRM Build Priority List and Research Findings

## Why this document exists

Everything in this document was worked out live, in conversation, across a single long session. The checklist alone is not enough — a bare list of task names loses the *reasoning* behind why each item is placed where it is, what risk it carries, what was debated about it, and what was ultimately decided and why. This document exists to preserve that reasoning permanently, in a place that survives beyond any one chat window.

Nothing in this document is a locked spec the way the CRM Build Contract addenda are. This is a living priority list, expected to be edited, reordered, and argued with as work progresses.

---

## Part 1: The Backend Booking Sequence — COMPLETE

All seven items below were built, tested with real red/green cycles where applicable, reviewed diff-by-diff, and pushed to `origin/main`. This entire sequence is done.

### 1. Availability Window model, schema, migration — COMPLETE, committed at `426af69`

One row per recurring weekly time block for one staff member. A deliberate tradeoff was made and documented in the model's own docstring: `meeting_duration_minutes` and `daily_cap` are logically per-staff settings but were stored per-window to avoid touching `users` and keep the migration to one table. This remains a known, accepted tradeoff — it did not block the booking engine, since slot computation (item 3) simply reads whichever window applies to the day being computed. The database enforces a `UniqueConstraint` on `(user_id, day_of_week)`.

### 2. Availability Window CRUD endpoints — COMPLETE, committed at `48eef23`

Real API endpoints with a stated RBAC assumption: any staff member can view all windows in the firm, but can only create/update/delete their own, unless they are a `firm_owner` or `manager`. Tested with a real watched red/green cycle proving a raw 500 error correctly becomes a clean 409 on a duplicate-day attempt.

**Update, 2026-08-15:** Andrew's own baseline run found that the duplicate-day check's error-code detection (`getattr(exc.orig, "pgcode", None)`) is written for `psycopg2` but he reported his environment running `psycopg3`, where the attribute is `sqlstate`, not `pgcode`. Investigating this directly on Ben's machine produced the **opposite** empirical result: `DATABASE_URL` has no driver override, a real traceback shows `psycopg2.errors.ForeignKeyViolation`, and `psycopg2.errors.UniqueViolation` was directly confirmed to have `pgcode=True`, `sqlstate=False`. The guard test passes cleanly on a freshly rebuilt database with the current, unmodified code. This is now a real, open, unresolved contradiction between two environments, escalated to Andrew directly rather than guessed at in either direction. See "Open Findings From Tonight" below. No code changed as a result of this — applying either party's fix blind could break the other party's working environment.

### 3. Booking model — COMPLETE, committed at `e68fa2a`

One row per real scheduled meeting. `location_snapshot` deliberately freezes the meeting location at booking time so a later change to a staff member's setting never silently rewrites a past booking's confirmation record. A real design correction was made after initial review: `staff_user_id`'s delete behavior was changed from `SET NULL` to `RESTRICT` at Ben's explicit direction, so a staff member with real booking history cannot be deleted at all — historical attribution for the intelligence layer must never be silently lost. Proven with a real `psycopg2.errors.RestrictViolation` caught and asserted on directly, plus a companion test confirming a staff member with no history can still be deleted normally.

### 4. Meeting location setting — COMPLETE, committed at `8fb87d9`

Per-staff `meeting_location_type` (video/phone/office) plus `meeting_location_value` added to `User`. Both nullable. A real near-miss was caught and corrected here: the `BookingStatus` enum from item 3 had never actually been committed — it existed only on disk, meaning the real, pushed repository would have failed to import `Booking` at all. Caught by noticing `BookingStatus` appearing as "new" in a diff that should only have contained `MeetingLocationType`, confirmed via `git show HEAD:app/core/enums.py`, and folded into this commit with an honest message naming what happened.

### 5. Slot computation — COMPLETE, committed at `4565c90`

The real math: availability windows minus buffers minus daily cap minus existing bookings, computed fresh on every call, never cached. Directly informed by outside research: buffers are per-booking protected windows, not pre-subtracted from the raw schedule, and can legitimately stack between adjacent bookings. Proven with a real watched-fail cycle: a wrong "fully contained" overlap check was shown wrongly offering a partially-overlapping slot, then corrected to a proper "any overlap" check. A second near-miss was caught here too — `Lead.bookings`, the other half of the Booking-Lead relationship, had also never been committed since item 3; found and fixed the same way as the `BookingStatus` gap.

A follow-up cleanup task promoted three shared helper functions (`get_window_for_day`, `slot_conflicts_with_booking`, `ACTIVE_STATUSES`) from private, underscore-prefixed names to genuinely public ones, since `booking_service.py` (item 6) was already importing them across the module boundary. Pure rename, zero behavior change, committed separately at `bea6ceb`.

### 6. The booking action endpoint — COMPLETE, committed at `1920609`

Claims a real slot, creates a `Booking`, transitions the lead to `call_booked` via the existing `transition_lead_stage` function, and fires `lead.call_booked` — which the goal-jump mechanism (built earlier in the nurture engine work) picks up automatically with zero additional wiring, confirmed directly from the code. This is the first use of `SELECT ... FOR UPDATE` row-level locking anywhere in this codebase, proven with a real watched-fail cycle: with the lock removed, two concurrent booking attempts for the same slot both wrongly succeeded; with it restored, only one does. The booking write and the lead-stage transition are atomic within one transaction — a lead that cannot legally move to `call_booked` (e.g., already `won`) gets no `Booking` row created for it either. Staff-facing only; public lead self-booking is deferred until Andrew's public intake endpoint exists.

### 7. Post-call outcome handling — COMPLETE, committed at `202b620` and `921fc57`

Built in two parts with a mandatory checkpoint between them, because reconnaissance found the contract actually describes this as "a one-click staff mark from the task," not the three-button notification originally assumed — the existing notification service has no way to carry structured choices, so this had to be Task-based.

**Part A:** a scheduler sweep (matching `deadline_scheduler.py`'s exact pattern) detects `Booking` rows past their `end_time` still marked `scheduled`, creates a real `Task` for the staff member with an idempotency guard preventing duplicates on repeat ticks. Also built `reactivate_enrollment`, a genuinely missing function confirmed absent from the entire codebase — the reply-pause mechanism built earlier could pause an enrollment but nothing could ever un-pause one.

**Part B:** the outcome-marking endpoint and its three branches. `call_held` completes the booking and reactivates any paused enrollment. `not_a_fit` completes the booking and transitions the lead to `lost`. `no_show` marks the booking `no_show` and checks a reschedule cap — implemented as a live count of prior `no_show` bookings for that lead rather than a separately-maintained counter column, which cannot drift out of sync with reality the way a counter could.

**A real bug was found and fixed before commit:** `_apply_not_a_fit` was firing `log_event(event_type="lead.call_held", ...)` — mislabeling a not-a-fit outcome under the wrong event name in the permanent behavioral history. The fix removed the event entirely rather than renaming it, since `transition_lead_stage` already fires `lead.lost`, which is the complete and correct record — no dedicated event name exists in the contract for this specific outcome. Proven with a real watched-fail cycle, and a genuine test gap was closed at the same time: the original test never queried `BehavioralEvent` at all, only checked booking/lead/task state, and would never have caught this bug.

Two honest open findings from this task, not yet resolved:

- The contract says the no-show reschedule loop is "capped at 2" but does not specify what happens once the cap is reached. The `cap_reached` flag fires correctly into the event metadata, but no further action is taken automatically. A lead could sit in this state indefinitely with nobody told. Needs a real decision — likely worth asking Andrew, similar to the earlier `condition_label` question.
- `LeadLostReason` has no `not_a_fit` value; `other` is used as a temporary placeholder. A dedicated value would be cleaner but adding one requires Andrew's sign-off, since event names freeze after first deploy per section 9.1.

---

## Part 2: Open Findings From Tonight, Requiring Andrew's Input Before Proceeding

### The pgcode/sqlstate driver contradiction

Andrew's baseline found the availability-window duplicate-day check broken under what he identified as `psycopg3`. Ben's independent, empirical check on his own machine found the opposite: `psycopg2` is genuinely in use, the existing code is correct for that driver, and the guard test passes cleanly against a freshly rebuilt database with zero code changes. Both findings are real and empirically confirmed on their respective machines. The most likely explanation is that the two environments are running different Postgres drivers, not that either person's diagnosis is wrong. Escalated to Andrew directly with the full empirical evidence, asking him to check how the driver is actually pinned (`requirements.txt` / lockfile) and confirm which one is canonical, since applying either suggested fix blind risks breaking whichever environment is not currently broken. No code changed. Waiting on his reply.

### `delete_engagement` guard — still not built

Real, known, severe data-loss bug found in the project's own Consolidated Roadmap document hours into this session: deleting an engagement does not check for attached documents, time entries, or invoices before deleting, and the permanent event log misrepresents the outcome as `engagement.archived` when the true outcome was permanent destruction. Described in the roadmap itself as a small fix, matching an existing pattern already used for invoices, requiring no migration. Placed in the priority list by severity, not build-sequence order. Not yet touched. This is the next actionable, unblocked item as of this update.

### Scheduler multi-worker safety — RESOLVED, no longer open

Andrew confirmed directly: production runs two Gunicorn workers by design, and the existing single-host `fcntl` lock is built for exactly that case, not despite it. He watched it work correctly in the real Aug 14 deploy journal — both workers started, exactly one acquired the lock, the other stood down, all 14 jobs registered exactly once. The concern raised in this session's research was reasonable to check but is now a confirmed non-issue.

### Gmail scope removal — half complete

Andrew's backend-side scope removal landed (`5a18752`, confirmed in git log: "remove the Gmail OAuth scopes and ship email sync disabled by default"). He also added a tripwire test asserting the requested scope list contains nothing Gmail-related, so code and console cannot silently drift apart again after this lands. He gave explicit go-ahead for Ben to do the console-side removal now, since the mismatch window is small and nothing currently uses Gmail scopes anyway. **The manual Google Cloud Console step itself has not been confirmed done as of this update.**

### Test database stability — reinforced, still needs Andrew's buy-in

A second real stale-database incident happened tonight, independent of the first one earlier in the session: accumulated test runs across multiple Claude Code sessions (including at least one credits-limit restart) left `jammpx_test` in a degraded state producing 286 failures and 1495 errors on a supposedly clean baseline. Resolved the same way as before — confirmed no stray processes, dropped and rebuilt the schema from genuinely empty, confirmed a clean return to the known-good baseline shape. This is now the second independent occurrence of the exact failure mode the transaction-rollback research (Finding R1, below) was proposed to structurally eliminate. Still not built, still requires Andrew's buy-in since `tests/conftest.py` is shared infrastructure. The case for raising this with him soon has gotten stronger, not weaker, since the original recommendation.

### Notification taxonomy — RESOLVED, no longer parked

Andrew delivered the final ruling. Three tiers, with a stated test for placement: **loud** (immediate push) means a human is needed or waiting right now; **quiet** (notification center plus digest, no push) means the owner should learn it happened without being interrupted; **silent** (timeline only, no notification object) means it exists in the lead's history and nowhere else.

Every loud and quiet notification must explain *why* it fired in plain language with real specifics (who, what sequence, which question, which answer) — never a bare event name. Andrew was explicit that his example wording is illustrative only, not final copy; the actual writing is Ben's to do well.

**Loud:** a lead replying (automation pauses, human is literally waiting on a human); a call being booked (the happy-path payoff, delivered with the full summary card).

**Quiet:** a lead being disqualified (must name the specific triggering question and answer — this is real, durable, intelligence-layer data, not just a UI string); a form being abandoned, but only as the *last* step of a real recovery attempt the system makes on its own first (partial save, a wait, a nudge email to the lead, another wait, and only then a quiet digest line — never a notification at the moment of abandonment itself). Wait durations for this chain are sequence configuration, not hardcoded constants, so firms can tune them later; sensible defaults should be picked and documented, not invented arbitrarily.

**Silent:** unsubscribing (never even whisper the temptation to chase someone who opted out — a real compliance and product-integrity decision, not an oversight; still tracked via the behavioral event log for aggregate intelligence-layer use, just never surfaced as a notification); routine sequence completion without conversion; genuinely cold non-engagement (ad clicks, page visits, a lead who never touches the form); an owner reactivating their own paused enrollment (they already know, telling them is noise).

One real gap worth naming: the abandoned-form escalation chain this ruling describes assumes infrastructure — form-abandonment detection — that does not exist anywhere in tonight's build. This is confirmed future scope, not something partially built and forgotten.

---

## Part 3: Deferred to Their Own Session (Unchanged)

### Pipeline UI, including the won-transition confirmation dialog

Confirmed by direct reconnaissance: no lead-related frontend screen exists anywhere in this codebase — no list view, no detail view, no API calls from the frontend to any of the five real lead endpoints that already work. The reusable confirmation-dialog component (`useConfirm`) already exists and is used elsewhere, but has nowhere to attach to yet. The contract describes the real lead detail view as a major, unified surface, explicitly warning against building "four partial context displays" instead of one real one. Deferred to its own dedicated session rather than built sight-unseen late at night.

### Booking-facing frontend UI

Depends on the pipeline UI existing first, and on Andrew's public intake config endpoint for any lead-facing (non-staff) booking flow.

---

## Part 4: Research Findings (Perplexity Deep Research), In Full, With Devil's Advocate Reasoning

*(Unchanged from original — preserved in full below for continuity.)*

### Finding R1 — Test Database Stability

TRUNCATE-based cleanup requires an ACCESS EXCLUSIVE lock on every table it touches, a structural deadlock risk under any concurrency. Transaction-rollback cleanup requires no such lock and was cited as roughly 80x faster in real-world reports. A companion Postgres advisory lock at session start would catch accidental concurrent test-suite invocations automatically. **Devil's advocate:** `tests/conftest.py` is shared infrastructure Andrew's own tests run through; this is a strong recommendation to bring to him, not something to unilaterally rewrite. **Status update:** this failure mode has now recurred twice independently in one session, strengthening rather than weakening the case for raising it soon.

### Finding R2 — APScheduler and Multi-Worker Production Safety

A single-host `fcntl` lock is correct and commonly recommended, but only for single-host deployments; uncoordinated multi-worker scheduler instances cause confirmed duplicate job firing. **Devil's advocate:** nothing was actually broken; the real open question was a fact only Andrew controlled. **Status update: resolved.** Production runs two workers by design, and Andrew confirmed the lock works correctly for exactly that case, observed directly in a real deploy journal.

### Finding R3 — Duplicate Detection, Lead Routing, No-Show Recovery

Established CRMs match duplicates primarily on email, flagging for human review rather than auto-merging except on exact matches. Layered lead routing (dedupe check, then territory, then workload, then quality signal) outperforms bare round-robin. No-show recovery should be fast (5-15 minutes), multi-channel, low-pressure, and tracked as its own sub-stage rather than folded into "lost." **Devil's advocate:** duplicate detection risks real harm on a false positive if auto-merge is too aggressive; automatic lead routing may be solving a problem JAMM's near-term 2-to-40-staff customers don't have — raised directly, kept on the list at Ben's explicit direction anyway. No-show handling turned out to independently confirm a decision Andrew had already made before this research ran.

### Finding R4 — Accounting-Specific CRM Feature Gaps

Proposal-to-engagement handoff, lead-source ROI reporting, and referral-partner tracking are all real gaps relative to named competitors (Karbon, TaxDome, Canopy, Financial Cents, and others), with referral-partner tracking being a genuinely open lane no named competitor offers natively. Lost-reason analysis benefits from a layered taxonomy rather than one flat field; JAMM's existing `LeadLostReason` already clears the baseline bar. Real user complaints across G2/Capterra/Reddit describe CRM functionality in this category as frequently feeling like an afterthought — direct, if accidental, validation of JAMM's foundational design principle. **Devil's advocate, most consequential item:** referral *fee calculation and payout* carries real compliance risk under AICPA rules (referral fees are forbidden on attest clients, and disclosure/consent must be documented) and was deliberately separated from the low-risk scorecard-only tracking feature. Explicit decision: not to be built speculatively — requires a real strategic conversation with Andrew first, compliance-aware design second, code third.

---

## Part 5: The Full Priority List, In Order, As It Currently Stands

1. ~~Booking model + migration~~ — DONE (`e68fa2a`)
2. ~~Meeting location setting~~ — DONE (`8fb87d9`)
3. ~~Slot computation~~ — DONE (`4565c90`, `bea6ceb`)
4. ~~The booking action endpoint~~ — DONE (`1920609`)
5. ~~Post-call outcome handling~~ — DONE (`202b620`, `921fc57`)
6. **`delete_engagement` guard — NEXT. Real, severe, unblocked, not yet started.**
7. ~~Scheduler multi-worker safety~~ — RESOLVED, confirmed safe by Andrew
8. Gmail scope console removal — half done (Andrew's backend half landed); Ben's manual console step not yet confirmed
9. Pipeline UI, including the won-transition confirmation dialog — its own dedicated session
10. Booking-facing frontend UI — after pipeline UI and the public intake endpoint both exist
11. Test database stability fix, transaction-rollback instead of TRUNCATE — needs Andrew's buy-in; case reinforced by a second independent incident tonight
12. Onboarding checklist + intake questionnaire auto-triggered on `won`
13. Referral partner scorecard (tracking only)
13a. Referral fee calculation and payout — explicitly not to be built speculatively; strategic and compliance conversation with Andrew required first
14. Lead source ROI dashboard
15. Lost-reason reporting dashboard
16. Duplicate lead detection — flag-for-human-review only, auto-merge restricted to exact email match
17. Automatic lead routing/assignment — kept in the list at Ben's explicit direction, despite a real, raised caution that it may be better suited to larger firms than JAMM's near-term 2-to-40-staff target customer
18. Capacity-based intake gating — no established industry pattern exists to copy; if built, must require explicit human confirmation to activate, never auto-pause lead intake unilaterally
19. ~~Notification taxonomy~~ — RESOLVED, full three-tier ruling delivered by Andrew, ready to build whenever prioritized

**Open, unresolved, waiting on Andrew before any related code changes:** the pgcode/sqlstate driver contradiction (Part 2).
