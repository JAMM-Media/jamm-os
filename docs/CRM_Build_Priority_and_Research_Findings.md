<!-- Created 2026-08-14/15 during a live build session. Updated 2026-08-15 to reflect the completed backend booking sequence and two real bugs found and handled during the session. Updated again 2026-08-17 to reflect the resolved driver contradiction, the duplicate-day guard fix, the complete staff-facing booking UI, and the complete firm timezone system. This document captures the full reasoning behind every item on the priority list, not just the item itself, so context is never lost to a closed chat window. -->

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

## Part 1B: Staff-Facing Booking UI and Firm Timezone System -- COMPLETE (2026-08-17)
Built in the session immediately following Part 1's completion. All items below were built, reviewed diff-by-diff against real output (never a trusted summary), tested with real watched-fail cycles where applicable, and pushed to origin/main.

### Pipeline UI -- COMPLETE
Built as a split-pane layout: a persistent table on the left, a URL-driven detail panel on the right. Includes a real activity timeline pulling from LeadMessage and BehavioralEvent, a StageProgressBar, contextual quick-action buttons per stage, and a summary strip with real per-stage counts. Page title is "Pipeline," not "Leads" -- a deliberate, permanent decision. Three real structural bugs found via live browser DOM measurement during this build (summary strip unmounting on filter change, skeleton row count not tracking real count, skeleton missing a header row causing a ~49px jump on every transition) were all fixed in the same session.

### Two real backend gaps found and closed before the booking UI could work at all
compute_available_slots() existed and worked but was never exposed over HTTP -- no endpoint anywhere called it. GET /users/ (the only staff-listing endpoint) requires firm_owner, so a regular staff member could not populate a staff picker. Both fixed:
- GET /api/v1/bookings/slots -- wraps compute_available_slots, staff-accessible, tenant-scoped, 60-day range cap.
- GET /users/bookable-staff -- staff-accessible, returns only id and full_name (no email, role, or other HR data) for users who have at least one AvailabilityWindow configured. Deliberately narrower than GET /users/, matching the existing RBAC pattern on availability-windows where team scheduling visibility is open to all staff but full HR data is not.
- GET /api/v1/bookings/ with an optional lead_id filter -- needed so the frontend could show a lead's existing booking.

### A real bug found in existing code: "Book Call" was bypassing the entire booking engine
The contacted stage's Book Call quick action called handleTransition('call_booked') directly -- a bare stage change with no Booking row ever created, completely bypassing the row-level locking, slot-conflict re-check, and atomic stage transition built in Part 1. Fixed: Book Call now opens a real BookCallModal (staff picker, then real open slots grouped by day); the stage transition to call_booked now only happens as a side effect of a real booking being created via the existing create_booking() function, exactly as originally designed.

### Two real bugs found and fixed via direct browser verification, not caught by any test
- The Scheduled Call card never appeared after a successful booking. Root cause: the bookingsData useFetch call was never given its own refetch function, so onBooked never refreshed it. One-line fix, confirmed in the browser afterward.
- A pre-existing (not introduced by this session) full border box around the Book Call / Mark Lost / Other stage button row, caused by border-[0.5px] setting all four sides while border-t only overrode the top width, leaving the other three sides visible. Fixed by removing the redundant border-[0.5px] utility.

### Firm timezone system -- COMPLETE
Real gap found via direct browser test: AvailabilityWindow times were being treated as UTC directly with zero timezone conversion -- explicitly documented as "out of scope" in slot_computation_service.py's own docstring. A 9am-5pm window displayed as 5am-1pm in the browser. Fixed with a real, three-part build:
- Backend: Firm.timezone (String, server_default America/New_York as a safe migration value only, not a design assumption), migration b2321b6bb22a. slot_computation_service.py and booking_service.py both localize AvailabilityWindow times using the firm's real timezone via zoneinfo before converting to UTC, replacing the previous direct-UTC-tagging. Proven correct with a real watched-fail cycle and five new tests in test_slot_timezone.py covering LA, NY, Chicago, and UTC, deliberately including a January/July pair for Los Angeles to catch the PST/PDT DST boundary, not just a single fixed offset. Existing slot/booking tests updated to set timezone explicitly rather than relying on an implicit UTC assumption -- no existing assertions were changed, only made explicit.
- Frontend: a real Timezone setting added to Settings > Firm, a six-option dropdown (Eastern/Central/Mountain/Pacific/Alaska/Hawaii) wired to the existing PATCH /firms/me endpoint, so a firm outside Eastern time has a real way to correct the migration default. Verified in the browser: setting a firm to Pacific correctly shifted a 9am-5pm window's displayed slots by the correct three-hour offset relative to Eastern.
This closes a real correctness gap that would otherwise have silently shown every non-Eastern firm the wrong booking times with no way to fix it.

---

## Part 2: Open Findings From Tonight, Requiring Andrew's Input Before Proceeding

### The pgcode/sqlstate driver contradiction -- RESOLVED
Andrew ran a full check across production, the repo's dependency pins, and CI. Verdict: psycopg3 is canonical everywhere that counts -- production runs psycopg 3.3.4 with no psycopg2 in the venv, requirements.txt pins psycopg[binary] only, and CI has never run psycopg2. The real root cause was neither environment being misconfigured: .env.example -- the file the README tells every new setup to copy -- has carried a plain postgresql:// prefix since June 2. SQLAlchemy selects its driver from the URL prefix, not from what happens to be installed, so a plain prefix silently selects psycopg2 whenever it is importable, which it was on both Andrew's and Ben's machines because create_test_db.py imports it and it appears in no requirements file. Same repo, same real packages, one string different in a file nobody had reason to suspect. "Which driver is installed" was never the right diagnostic question.
Andrew fixed .env.example, updated the README's copy-env step to state the prefix requirement and why, added tests/test_database_url_prefix.py as a permanent tripwire (asserts both the resolved settings URL and the template itself carry the correct prefix), removed a hardcoded plain-prefix fallback in test_auth.py, and corrected the conftest docstring example. Landed as ad5674f, on main as 5815afd.
Ben's local fix: corrected DATABASE_URL in both .env and .env.test to the postgresql+psycopg:// prefix, confirmed via a real engine.dialect.driver check returning "psycopg", and confirmed tests/test_database_url_prefix.py passes locally. The known 10-failure baseline from the first full-suite run of the 2026-08-17 session is now back to 9 -- this was never a ninth pre-existing failure, it was this exact bug surfacing for the first time in a complete run.
Incidental corroboration: the availability-window duplicate-day guard's failing test (see below) errored with psycopg.errors.UniqueViolation -- a real psycopg3 exception with no .pgcode attribute -- directly confirming the guard's 409 branch was unreachable dead code, independent of and consistent with Andrew's diagnosis.

### Availability-window duplicate-day guard -- RESOLVED
The guard in app/crud/availability_window.py read exc.orig.pgcode, a psycopg2-only attribute that does not exist on a psycopg3 exception. This meant the check pgcode == "23505" always evaluated None == "23505" -> False, so the guard's 409 branch was permanently unreachable -- a real duplicate-day attempt fell through to an unhandled 500 instead of a clean 409, and no automated test existed anywhere to catch this; the 409 path had only ever been verified by hand.
Fixed to read exc.orig.sqlstate first, with a defensive fallback to .pgcode in case the driver ever changes again. A real guard test was written and does not just claim correctness -- it was watched fail first (reverted to pgcode-only, confirmed a genuine unhandled psycopg.errors.UniqueViolation escaping instead of a caught ValueError), then watched pass again after the real fix was restored, then confirmed via git diff that the restore left no stray changes. Committed at 06c59fa.

### `delete_engagement` guard — still not built

Investigated directly against the real, current codebase during the 2026-08-17 session and found already fixed -- not the severe open bug this document originally described. A real guard exists checking for attached documents, time entries, and invoices before allowing deletion, and the permanent event log correctly fires engagement.deleted, not the previously-assumed engagement.archived. Verified empirically against production via a direct API call that refused deletion of an engagement with an attached document.
One real, still-open question surfaced during this same investigation: whether the cascade-delete behavior on the 8 CASCADE foreign keys pointing at engagements (document_requests, extensions, tax_organizers, engagement_members, time_entries, qc_checklist_items, recurring_engagement_log, tasks) is intentional across all 8, or whether some should be blocked like the three checked types above rather than cascading silently. The full list, with a one-line description of what each table holds, was sent to Andrew directly. He has asked to rule on all 8 at once, sorted into work-product-vs-overhead, rather than deciding a few and leaving others unexamined. Awaiting his ruling.

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

Nothing currently deferred as of 2026-08-17. Both items previously listed here (Pipeline UI, Booking-facing frontend UI) are complete -- see Part 1B.

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
6. ~~`delete_engagement` guard~~ -- ALREADY FIXED, confirmed via direct investigation 2026-08-17. See Part 2. Open sub-question (8-FK cascade classification) sent to Andrew, awaiting his ruling.
7. ~~Scheduler multi-worker safety~~ — RESOLVED, confirmed safe by Andrew
8. Gmail scope console removal — half done (Andrew's backend half landed); Ben's manual console step not yet confirmed
9. ~~Pipeline UI~~ -- COMPLETE 2026-08-17. See Part 1B.
10. ~~Booking-facing frontend UI (staff-facing half)~~ -- COMPLETE 2026-08-17. See Part 1B. Lead-facing self-booking half still deferred, depends on Andrew's public intake endpoint.
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
20. ~~Firm timezone setting for non-Eastern firms~~ -- COMPLETE 2026-08-17. See Part 1B.

**Open, unresolved, waiting on Andrew:** ruling on the 8-FK engagement cascade-delete classification (Part 2). The pgcode/sqlstate driver contradiction is RESOLVED -- see Part 2.
