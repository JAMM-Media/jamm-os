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

**Finding: RESOLVED 2026-08-18.**
_derive_source_platform() added to app/api/intake.py, called before LeadCreate on every intake submission. Maps ten real platform values plus common aliases (fb, ig, twitter) to SourcePlatform, defaults any unrecognized utm_source to SourcePlatform.other, leaves source_platform null when utm_source is absent, and deliberately never produces the four cold_outreach-reserved values (email, phone, dm, direct_mail) -- covered by an explicit guard test. 7 new tests added to tests/test_intake_endpoint.py; all 10 pre-existing intake tests and all 21 intake pricing config tests confirmed still passing. Committed at 61cdb0b.

### 2. Nurture preset tree content (Contract sections 6, 11)

**Finding: RESOLVED (structure only) 2026-08-18. Real email sending is a separate, still-open follow-up -- see the new item below.**
Andrew's real reference tree artifact (jamm_nurture_preset_tree.html, previously referenced by the contract but missing from the repo) was obtained and saved at docs/jamm_nurture_preset_tree.html. The full 75-node graph (3 triggers, four phases, long-term drip) is now seeded per-firm on firm creation via app/services/nurture_preset.py's seed_firm_nurture_preset(), parsed from the real tree file rather than hand-transcribed, following the same seeding pattern already used for automation presets and letter templates. A backfill script exists at scripts/seed_nurture_preset.py for firms created before this landed.
One deliberate addition beyond the source artifact: a new node D7 ("Long-term drip exhausted") plus two loop caps, both required by Contract section 6.1's "no uncapped loop ever ships" rule, which the raw tree did not itself satisfy at two points. 39f->25 (the alt-channel booking retry loop) is capped at 2, mirroring the already-contract-ratified rebook loop, routing to the existing D3b dead end. LD4->14 (drip re-entry into Qualification) is capped at 3, routing to the new D7 node. Both were deliberate judgment calls made with Ben directly, not invented unilaterally by Claude Code, and are worth a heads-up to Andrew as a real, if small, structural addition to his diagram.
Every email-type step in the seeded graph carries a placeholder config (subject/body keys present but unfilled, pending the real content session) -- the graph is structurally complete and inert. No email actually sends as a result of this work. 14 new tests in tests/test_nurture_preset_seed.py cover node/edge counts, structural integrity, tenant isolation, duplicate-seed safety, and full graph reachability via BFS from all trigger nodes (including LD1, a fourth trigger node inside the drip loop that was not originally anticipated in the task's scoping but is correct per the source tree). The reachability test was watched-fail-verified by hand before being trusted: the LD4->D7 edge was temporarily removed, the test correctly caught the resulting orphaned node, the edge was restored, and the test was confirmed green again. Full backend suite re-run clean afterward: 1115 passed, the same known 9 pre-existing Stripe webhook failures, zero regressions. Committed at 3edf259.

### 2a. Real email sending against the now-seeded graph (new, 2026-08-18)

**Finding: OPEN. The graph is real; nothing sends yet.**
run_nurture_tick() in app/services/nurture_execution_service.py can walk the seeded graph forward (confirmed capable of enforcing loop_cap, resolving wait_until_event vs wait_fixed, and firing goal jumps -- verified via the existing test_nurture_execution.py suite passing cleanly against the newly seeded data). But no code anywhere in the codebase actually sends an email through Postmark for a nurture step -- confirmed by grep, no Postmark send wrapper exists in app/services/ at all. Every email-type step's config is placeholder-only pending the copy session referenced in item 3's brainstorm work.
**What remains:** build the actual Postmark send integration for email-type steps (subject/body rendering, the marketing/broadcast stream per Contract section 6.6, unsubscribe link injection, suppression list check before send), wired into run_nurture_tick(). This unblocks answer-button email links (old item 3, renumbered below), since a button embedded in an email needs a real, sent email to attach to.

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


### 10. Public intake form structure and context-question brainstorm (new, 2026-08-18)

**Finding: TWO NEW SOURCE DOCUMENTS RECEIVED, NEITHER YET ACTED ON.**
Andrew sent two documents on 2026-08-17/18, now saved at docs/Public_Intake_Form_Structure_Contract_v1.md and docs/JAMM_PX_Fee_Schedule_to_Intake_Form_Connected_Picture.md.

The first locks the intake form's structure: a four-step flow (broad service, engagement type, complexities, contact capture), with a hard governance rule -- structure is Andrew's, copy and the context-question inventory and visual design are Ben's, and any structural change is a conversation first, not a unilateral edit.

It also hands Ben a substantial, not-yet-started deliverable: a dedicated brainstorm session mapping the full context-question web for the entire top of the funnel (every context question a firm owner would want answered before a call, for every branch of Steps 1 and 2), pruned under a stated friction discipline, with conditional depth sketched explicitly for every surviving question, opt-out wording for each, and a rendering plan for the pre-call summary card. The output is a written document for Andrew to review before anything is built.

The second document confirms, verified directly against the live codebase, that the intake pricing config endpoint (app/schemas/intake_pricing_config.py, GET /intake/{slug}/pricing-config) genuinely matches Addendum 2's flat-question-list design, and names two real gaps not previously documented in this file:

- The endpoint currently ignores per-engagement-type scope, ruled fixed on 2026-08-17 but not yet built. A dimension configured only as an override for one engagement type currently incorrectly surfaces as a question under every service its flag maps to. Andrew states the response shape will not change when this lands, only which questions populate each service's list. Lands in his next backend session.
- There is no design yet for how a lead's complexity-question answers persist on submit. IntakeSubmitBody currently carries no complexity answers at all. Explicitly flagged as needing agreement with Andrew before Ben builds it, not something to design unilaterally.
- IntakeSubmitBody accepts how_did_you_hear but does not persist it; no column exists. A future attribution_notes column is noted in code comments but not built.

**What remains:** (a) the brainstorm session itself, producing the written context-question document for Andrew's review; (b) once Andrew's scope-aware pass lands, confirm the frontend intake form still works correctly with more precise per-service question lists; (c) agree with Andrew on the submit-time payload shape for complexity answers before building the submit-side persistence; (d) decide the how_did_you_hear / attribution_notes gap, likely alongside the still-open referral-source required-field decision already tracked in this document.

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

1. ~~UTM-to-source_platform auto-derivation~~ -- COMPLETE 2026-08-18. See Part 2.

2. ~~Nurture preset tree data~~ -- COMPLETE (structure only) 2026-08-18. See Part 2. Real email sending is now the actual blocker -- see item 2a below.

2a. **Real email sending against the seeded graph** -- the actual next unblocked item. Postmark integration for email-type steps: subject/body rendering, the marketing/broadcast stream, unsubscribe link injection, suppression list check before send, wired into run_nurture_tick(). Depends on nothing else outstanding.

3. **Answer-button email links** (Contract section 5) -- now correctly sequenced after 2a, since a button embedded in an email needs a real, sent email to attach to. Once 2a lands: needs a signed URL scheme, a receive endpoint, and an intake form pre-fill path.

4. **Firm business-hours send window** (Contract section 6.1) -- should accompany or immediately follow the preset data build, since the preset will start sending real emails. Firm.timezone infrastructure is ready.

5. **R1 review-and-hold pattern** (Contract section 6.7) -- the unqualified decline email (R1 node) must be held for approval before the preset tree can be considered complete. Build as a step-level flag or a step type, not as a special-case R1 hack.

6. **Portal attribution survey** (Contract section 4.1) -- relatively self-contained. Depends on the portal notification system (already exists). Small build but important for data quality on legacy client books.

7. **Hot lead immediate alert** (Contract section 7.5) -- small, focused. Fire a Notification when is_hot is set to true, or when a lead arrives via intake with urgency indicating a hard deadline.

8. **Proposal generation** (Contract section 7.4, Addendum 1 section 6) -- last major phase; depends on Andrew's preset template completion. Do not start until template availability is confirmed. Build in this order: (a) propose service and generate draft from template with validate_context; (b) Accept answer button and click endpoint; (c) auto_send toggle and conditional e-sign trigger.

9. **Event-type string sign-off** (Contract section 9.1) -- coordinate with Andrew, not a build item. Should happen before the nurture preset tree goes live in any production firm, since sequence.* events will start firing at that point.

10. **Public intake form context-question brainstorm session** (new 2026-08-18 deliverable) -- not a code task. A dedicated planning session producing a written document for Andrew's review before any frontend intake form work begins. Should happen early, since the frontend intake form build (item 8's proposal phase aside) depends on knowing the full context-question set before implementation, not after.
