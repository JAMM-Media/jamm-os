<!-- Created 2026-08-17 as a section-by-section verification pass against the three governing CRM contract documents, cross-checked against the real current codebase. Supplements CRM_Build_Priority_and_Research_Findings.md. -->

# CRM Remaining Build Priority -- Verified Against Contract, 2026-08-17

This document is a section-by-section verification pass against the three governing CRM contract documents -- CRM Acquisition Tracker (August 12, 2026), CRM Build Contract Addendum 1 (August 12, 2026), and CRM Build Contract Addendum 2 (August 13, 2026) -- cross-checked against the real current codebase on 2026-08-17. Every claim in this document is backed by a real grep or file read run during the verification session, not assumption. Where evidence was ambiguous, the document says so.

It supplements, and does not replace, CRM_Build_Priority_and_Research_Findings.md. That document tracks the build history and session-by-session decisions; this one tracks contract coverage.

---

## Part 1: Confirmed Built and Verified

The following contract requirements were confirmed present in the codebase during this session and prior sessions.

**Lead model** (Contract section 8): `app/models/lead.py` confirmed present. Fields include: contact info, stage (LeadStage enum), lost_reason, referral_source (same ReferralSource enum as Client), source_platform (SourcePlatform enum), utm_campaign, utm_source, utm_medium, utm_content, utm_term, referring_client_id, referral_partner_id, service_interest, entity_type, revenue_band, urgency, hot flag, provenance (LeadProvenance enum), first_response_time. All five UTM fields confirmed in both the model and `app/api/intake.py`.

**ReferralPartner model** (Contract section 8): `app/models/referral_partner.py` confirmed present.

**Pipeline stages** (Contract section 7.1): LeadStage enum confirmed in `app/core/enums.py` -- identified, contacted, call_booked, proposal, won, lost. Lost reason enum (LeadLostReason: unqualified, unresponsive, chose_competitor, price, timing, other) confirmed. Won-transition creates a real Client record via `app/crud/lead.py`. Lost leads are not purged (no cascade delete on Lead).

**LeadProvenance and attribution precedence** (Contract section 3.3): LeadProvenance enum confirmed (crm_lead, firm_entered, client_reported). Precedence logic confirmed in `app/crud/lead.py` lines 11-13.

**ReferralSource enum** (Contract section 3.2): SourcePlatform enum confirmed in `app/core/enums.py` line 429, with docstring confirming the auto-derive-from-utm_source design intent. ReferralSource enum extended and in use on Lead model.

**Availability windows** (Contract section 7.2): `app/models/availability_window.py` confirmed. Per-staff weekly windows, meeting_duration_minutes, buffer_before_minutes, buffer_after_minutes, daily_cap. Meeting location type and value on User model. Firm.timezone for local time (migration b2321b6bb22a, 2026-08-17).

**Native booking with row-level locking** (Contract section 7.2): `app/services/booking_service.py` confirmed. SELECT ... FOR UPDATE in create_booking, atomic stage transition, location_snapshot, behavioral event fired. Booking model at `app/models/booking.py`. No-show recovery loop (capped at 2) in `app/services/booking_outcome_service.py`. Staff-facing BookCallModal in `frontend/src/components/leads/BookCallModal.tsx` (2026-08-17).

**Slot computation** (Contract section 7.2): `app/services/slot_computation_service.py` confirmed. Availability windows minus buffers minus daily cap minus existing bookings, computed fresh. Localized to firm timezone (2026-08-17). HTTP endpoint GET /api/v1/bookings/slots confirmed in `app/api/bookings.py`.

**Sequence engine infrastructure** (Contract section 6.1): `app/models/sequence.py` confirms Sequence, SequenceVersion (immutable), Step, StepEdge, SequenceGoal, Enrollment models. Step types confirmed in `app/core/enums.py`: email, wait_fixed, wait_until_event, condition, goal. Preset lineage key (preset_lineage_key) and step-level modified flag (is_modified_from_preset) confirmed in sequence.py. Channel field on Step (currently "email") confirmed at line 140. Versioning: every edit creates a new version, enrollments pin to version at enroll time, confirmed in model design.

**Goal-jump mechanism** (Contract section 6.1): `app/services/nurture_execution_service.py` confirmed -- SequenceGoal model, goal_event watched, enrollment jumps to target step when event fires.

**Stop conditions** (Contract section 6.1): unsubscribe confirmed in `app/services/unsubscribe_service.py`, suppressed email model at `app/models/suppressed_email.py`. Won-transition exits every sequence (confirmed in `app/crud/lead.py`).

**Inbound reply capture** (Contract section 6.5): `app/api/webhooks/postmark_inbound.py` confirmed. Postmark inbound webhook authenticates and attaches reply to lead thread. POSTMARK_INBOUND_WEBHOOK_USERNAME/PASSWORD in config.

**Public intake config endpoint** (Contract section 4, Addendum 1 section 9): `app/api/intake.py` lines 29-85 confirm GET /intake/{slug}/config and GET /intake/{slug}/pricing-config. `app/services/pricing_config_service.py` contains get_public_intake_config. 21 tests in test_intake_pricing_config.py and 10 in test_intake_endpoint.py confirm the endpoint is real and covered.

**Rate limiting on intake** (Contract section 9.2): `app/api/intake.py` lines 45 and 112 confirm rate limiting via slowapi -- 30/minute and 5/minute limits, plus a per-email rate check (3 requests per 900 seconds).

**EngagementType enum expanded to 43 types** (Addendum 1 section 2, Appendix A): Confirmed. The enum in `app/core/enums.py` lines 45-116 was counted directly and contains exactly 43 values, matching the full Appendix A list.

**merge-field validation (validate_context)** (Addendum 1 section 4): `app/services/letter_renderer.py` line 54 defines validate_context. `app/services/esign_service.py` line 95 calls it before any e-sign send. Confirmed wired into the esign path.

**Lead detail view -- Pipeline UI** (Contract section 7.3): `frontend/src/app/(app)/leads/[lead_id]/page.tsx` confirmed as a unified view -- source, answers (referral, stage), hot flag, full message thread (via LeadActivityItem), current stage, quick-action buttons. Split-pane layout with Pipeline table on left. Breadcrumb links back. StageProgressBar confirmed. All pipeline quick-actions confirmed wired (including booking modal for call_booked). Built 2026-08-17.

---

## Part 2: Verified Genuinely Open

### 1. UTM-to-source_platform auto-derivation (Contract section 3.1, Layer 2)

**Finding: OPEN. The field exists but the derivation is not implemented.**

utm_source is captured verbatim on the lead (confirmed in `app/api/intake.py` line 160). source_platform is a field on Lead (confirmed in `app/models/lead.py` line 58). The SourcePlatform enum's own docstring in `app/core/enums.py` line 429 says explicitly: "Auto-derived from utm_source whenever the lead arrived through a tracked link."

However: `grep -rn 'source_platform' app/api/intake.py app/services/` returned no results. The intake endpoint stores utm_source but never writes to source_platform. There is no mapping table, no derivation function, and no code path that translates utm_source="facebook" to source_platform=SourcePlatform.facebook.

**What remains:** write the derivation function (utm_source string -> SourcePlatform enum value, using the mapping facebook/instagram/tiktok/linkedin/youtube/x/google/bing/nextdoor/other), call it in the intake lead-creation path, set source_platform on the lead if utm_source is present, and enforce the precedence rule (a UTM-derived platform is never overwritten by a hand-picked one).

### 2. Nurture preset tree content (Contract sections 6, 11)

**Finding: OPEN. The engine exists; the actual preset sequence data does not.**

The nurture engine infrastructure is fully built (Step types, SequenceGoal, wait_until_event, goal-jump). But no seed script, migration, or fixture was found that loads the specific Phase 1 four-touch acquisition sequence described in Contract section 11:
- Four touches with 2/3/4/5-day escalating timeouts
- Rebook loop capped at 2
- Quarterly long-term drip with 90-day wait-or-engage check
- Drip re-entry landing at Qualification

`grep -rn 'Sequence(' scripts/` returned no output. `grep -rn 'seed_sequence\|nurture_preset\|acquisition_sequence'` across the entire repo returned only a reference in the CRM Acquisition Tracker doc itself. No Sequence, SequenceVersion, Step, or StepEdge rows are created by any existing script.

**What remains:** implement the full preset tree as described in the contract and the reference tree artifact (jamm_nurture_preset_tree.html). This is a substantial build: every node of the tree becomes Step rows, every edge becomes StepEdge rows, goal nodes become SequenceGoal rows, and the whole structure must be seeded per-firm on creation (or loaded as a system preset). Contract section 11 specifies the defaults; the reference tree artifact has the node IDs (T1, E2, E5, R1, etc.).

### 3. Answer-button email links (Contract section 5)

**Finding: OPEN. No answer-button rendering or click-handling exists.**

`grep -rn 'answer.*button\|answer_button\|answer_button_clicked\|lead.answer_button_clicked'` across `app/` returned zero results. The event type `lead.answer_button_clicked` listed in Contract section 9.1 as a candidate name does not appear anywhere in the codebase.

The contract states: "a question's options render as buttons; each button is a link with the answer baked in, so one tap records structured data and lands the prospect on the form with that question pre-filled." This is a complete subsystem: email template rendering that turns question options into click-links, an endpoint that receives the click, records the answer, and redirects to the pre-filled form.

**What remains:** build the answer-button URL generation (probably at email send time, encoding the answer and lead identifier into a signed URL), build the endpoint that receives the click, writes the structured answer to the lead, fires `lead.answer_button_clicked`, and redirects to the intake form with that question pre-filled.

### 4. Portal attribution survey (Contract section 4.1)

**Finding: OPEN. The client_reported enum value exists; the survey does not.**

`grep -rn 'client_reported'` confirmed the provenance enum value exists and the precedence logic (fills blanks only, never overwrites) is implemented in `app/crud/lead.py`. But `grep -rn 'attribution.*survey\|blank.*attribution\|portal.*survey\|pinned.*notification'` returned no results for any survey-related logic.

The contract specifies: a one-question survey for existing clients whose attribution is blank, riding the portal notification system as a pinned type that clears only on completion (not on read-all), never rendered when attribution is already set, answers writing with client_reported provenance.

**What remains:** identify which clients have blank referral_source (no attribution), create a pinned portal notification type for the survey, build the survey question UI in the portal, wire the submit to write the client's attribution with client_reported provenance and remove the notification.

### 5. R1 review-and-hold pattern (Contract section 6.7)

**Finding: OPEN. No review-hold or take-over mechanism exists.**

`grep -rn 'hold_for.*approval\|needs_review\|pending_review\|review_queue\|one.click.*take.over\|pull.*manual'` returned no results outside the concierge context (which is a different system). The concept of holding an outgoing email for owner approval before it sends does not exist anywhere in the codebase.

The contract requires: the unqualified-decline email (R1 on the tree) is held; the owner is notified with the lead's answers; the owner approves the decline in one click or overrides the lead back into the sequence. Additionally: every dead end notifies the owner with a one-click take-over that pulls the lead into manual mode.

**What remains:** implement the review-hold pattern as a standing automation feature -- a step type or a flag on steps whose external consequence requires human approval before firing. Specifically: hold the R1 decline email, create a Notification for the firm owner with the lead context, expose the approve/override actions. Also implement the dead-end notification with a one-click take-over that exits the lead from the sequence and marks it for manual handling.

### 6. Proposal generation (Contract section 7.4, Addendum 1 section 6)

**Finding: OPEN. No proposal send path exists.**

`grep -rn 'proposal'` in `app/api/` returned zero results outside the LeadStage enum value and comments. There is no proposal service, no proposal send endpoint, no accept-toggle setting, no Accept answer button logic, and no click-path to engagement letter.

validate_context exists and is used in `app/services/esign_service.py` for e-sign letters. But there is no proposal-specific send path that would call it, and no code connects the proposal stage to the engagement letter system.

The contract specifies (section 7.4): proposal generates from the firm's engagement letter template for the selected service type, sent unsigned; on Accept click (Addendum 1 section 6), a firm-level auto_send toggle governs whether the engagement letter sends immediately or holds for one-click approval; the accepted proposal becomes the e-sign engagement letter.

**Dependency flag (Contract section 7.4):** this phase explicitly depends on Andrew's engagement letter preset templates being ready (Build 2 on his track). Coordinate timing before starting this phase, not mid-build.

**What remains:** build the proposal send service (select template by service type, render with validate_context, send unsigned via email); the Accept answer button in the proposal email; the auto_send toggle as a firm setting; the accept-click endpoint that either auto-sends the e-sign letter or queues it for owner approval; the typed-reply pause (already handled by section 6.7's inbound reply logic if that's built first).

### 7. Event-type string sign-off (Contract section 9.1)

**Finding: NEEDS ANDREW'S SIGN-OFF BEFORE FIRST DEPLOY. Event types are in use but not formally blessed.**

The following event-type strings are currently in use in the codebase, confirmed by grep:
- lead.created
- lead.email_replied
- lead.call_booked
- lead.call_held
- lead.call_no_show
- lead.converted
- lead.lost
- lead.reopened
- lead.unsubscribed

The following candidate names from Contract section 9.1 are NOT yet in use (no code fires them):
- lead.stage_changed
- lead.form_started
- lead.form_submitted
- lead.answer_button_clicked
- lead.email_sent
- lead.email_clicked
- lead.call_rescheduled
- lead.proposal_sent
- sequence.enrolled
- sequence.step_advanced
- sequence.exited
- sequence.goal_reached

Contract section 9.1 states explicitly: "Andrew blesses the final event-type strings BEFORE first deploy because event names freeze forever once a firm is live." The 9 events currently in use have not been formally signed off per that process. This is not a build gap but a coordination gate -- no new event-type strings should be finalized until Andrew's sign-off, and the existing 9 should be included in that same review.

### 8. EngagementType enum expansion (Addendum 1 section 2, Appendix A)

**Finding: COMPLETE. The enum has exactly 43 values matching Appendix A.**

Confirmed by direct count: `sed -n '45,118p' app/core/enums.py | grep -c '= \"'` returned 43. The enum covers all categories from Appendix A: individual tax, business and entity tax, payroll and information reporting, sales tax, foreign reporting, bookkeeping and accounting, financial statements, advisory and representation, specialty, and catch paths (other_advisory, custom).

Note: ENGAGEMENT_TYPE_LABELS in `app/core/enums.py` provides display labels for all 43 values, and `tests/test_engagement_type_canon.py` enforces that every member has an entry.

### 9. merge-field validation before proposal sends (Addendum 1 section 4)

**Finding: PARTIAL. validate_context exists and is used in the e-sign path only; not wired to any proposal send path.**

`grep -rn 'validate_context'` confirmed: `app/services/letter_renderer.py` defines it (line 54); `app/services/esign_service.py` calls it (line 95) before any e-sign send. This is the correct pattern -- Addendum 1 section 4 specifies that a raw `{{fee_amount}}` must never reach a lead, and the esign path enforces that.

However, no proposal send path exists yet (see item 6 above), so there is nothing to wire validate_context into for proposals. The function is already correct and in the right place -- when the proposal send service is built (item 6), it must call validate_context before any automated external send, following the same pattern as esign_service.py.

**What remains:** call validate_context in the new proposal send service (part of item 6's build), using the same behavior: on any missing field, do not send, notify the firm owner with the specific fields, hold for review.

---

## Part 3: Real Open Questions for Andrew

### Event-type string sign-off (Contract section 9.1)

The 9 event types currently fired (listed in Part 2, item 7) need formal sign-off before first deploy, per the contract's own stated requirement. The remaining ~10 candidate names will be finalized as each corresponding feature (answer buttons, form events, sequence events, proposal send) is built. Recommend scheduling this review once the nurture preset data build is in progress, since that phase will introduce sequence.* events.

### Proposal phase dependency on engagement letter preset templates (Addendum 1 section 9)

The contract explicitly flags this: "today's engagement letter templates exist only as seed-run data, not as hard-coded system presets. Andrew is hard-coding versioned, lineage-keyed system preset templates as his own task. Your proposal step consumes those presets; since proposal is the last build phase there is runway, but coordinate timing at kickoff rather than discovering the gap mid-build."

As of 2026-08-17, it is not known whether Andrew has completed his preset template work. Confirm status before starting the proposal build phase. The proposal send service must have one confirmed template per service type available via lookup (engagement type in, template out) before it can function.

### Firm business-hours send window (Contract section 6.1)

The nurture engine does not currently implement the 8am-6pm firm-local send window. Emails are sent whenever the scheduler tick runs. This is not a blocker for the engine being functional, but it is a contract requirement (section 6.1: "Send windows: firm business hours, 8am to 6pm firm-local, configurable") that must ship before the engine is considered contract-complete. Firm.timezone is now available (2026-08-17), so the localization infrastructure is in place. The question is where in the execution loop to implement the window check -- clarify with Andrew whether the window should hold the email until the next business-hours window, or delay next_action_time to the start of the next window.

### Hot lead immediate owner alert (Contract section 7.5)

`grep -rn 'hot.*alert\|hot_lead.*notif'` returned no results. The hot flag exists on the Lead model and the UI surfaces it (Flame icon in the Pipeline table), but no immediate notification fires when a lead is marked hot or arrives hot from the intake form. The contract says: "Hot fires an immediate owner alert; hot leads should get a human same-day, not just the sequence." This is not currently built and was not investigated in prior sessions. Raised here for Andrew's awareness as a small, focused build.

---

## Part 4: Priority Order

Priority follows Contract section 10.1's stated build sequence (attribution -> intake form -> Lead/pipeline -> booking/availability/lead detail -> nurture engine -> proposal/conversion), adjusted for what is already substantially complete.

1. **UTM-to-source_platform auto-derivation** (Contract 3.1) -- small, surgical, unblocked. One function and one intake call. Should be done before the intake form goes live so attribution is exact from day one.

2. **Answer-button email links** (Contract section 5) -- part of the nurture engine completing. Required before any question-bearing email (E2, E5 in the tree) can function as designed. Needs a signed URL scheme, a receive endpoint, and an intake form pre-fill path.

3. **Nurture preset tree data** (Contract sections 6, 11) -- the engine infrastructure exists; loading the actual preset sequence data is the next substantial nurture build. Requires the reference tree artifact to be implemented step by step: every T, E, Q, R node becomes real Step rows, with timeouts matching section 11 defaults. This is the first time anything in the engine actually runs the acquisition preset rather than just being capable of running it.

4. **Firm business-hours send window** (Contract section 6.1) -- should accompany or immediately follow the preset data build, since the preset will start sending real emails. Firm.timezone infrastructure is ready.

5. **R1 review-and-hold pattern** (Contract section 6.7) -- the unqualified decline email (R1 node) must be held for approval before the preset tree can be considered complete. Build as a step-level flag or a step type, not as a special-case R1 hack.

6. **Portal attribution survey** (Contract section 4.1) -- relatively self-contained. Depends on the portal notification system (already exists). Small build but important for data quality on legacy client books.

7. **Hot lead immediate alert** (Contract section 7.5) -- small, focused. Fire a Notification when is_hot is set to true, or when a lead arrives via intake with urgency indicating a hard deadline.

8. **Proposal generation** (Contract section 7.4, Addendum 1 section 6) -- last major phase; depends on Andrew's preset template completion. Do not start until template availability is confirmed. Build in this order: (a) propose service and generate draft from template with validate_context; (b) Accept answer button and click endpoint; (c) auto_send toggle and conditional e-sign trigger.

9. **Event-type string sign-off** (Contract section 9.1) -- coordinate with Andrew, not a build item. Should happen before the nurture preset tree goes live in any production firm, since sequence.* events will start firing at that point.
