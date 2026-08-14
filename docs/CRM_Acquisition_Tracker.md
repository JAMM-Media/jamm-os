<!-- Converted from "CRM_Acquisition Tracker.docx", copied into repo 2026-08-14 -->

JAMM PX
CRM / Acquisition Tracker: Build Contract
Prepared by Andrew for Ben. August 12, 2026. This document plus the accompanying reference tree artifact (jamm_nurture_preset_tree.html) are the complete build specification. Everything in Sections 1 through 9 is decided; Section 10 lists your degrees of freedom; Section 11 lists the small set of defaults you build as-written unless Andrew revises them at kickoff.

# 1. What this is and why it exists
The acquisition tracker (working name; final product name is deferred until the intelligence layer is done, so the loaded word CRM never appears in UI copy) is a narrow, accounting-firm-specific tool for tracking potential clients from first contact through signed engagement: lead capture, source attribution, pipeline stages, nurture, qualification, booking, proposal, conversion.
Its primary identity is a data sensor, not a sales suite. JAMM's operational data and the behavioral event log both begin the moment someone is already a client. Everything upstream of that moment, the inbound channel, the source, the path that brought them in, is invisible to the entire product. This feature is the only thing that can perceive the step before the client exists. It is the sensor for the front of the money path, and with it JAMM sees the whole path end to end: acquisition at the front, workflow and operations in the middle, expansion and retention at the back.
It ships pre-launch because the product pitch names client intake as the first pillar, and that pillar must exist in the product before it exists in copy. Build ownership: Ben builds the feature full stack (backend and frontend). Andrew wires the intelligence into it afterward. The intelligence dashboards that consume this data (Best-Client Profile, acquisition surfaces) are a separate later build and are NOT part of this contract.
# 2. What it is not
•    Not Salesforce or any generic horizontal sales suite. Narrow and accounting-specific by design.
•    Not a scraper. The autonomous lead-scraping idea was killed: legal and ToS exposure, reputational asymmetry for compliance-sensitive firms, and the public data is too thin to qualify the ICP anyway.
•    Not an externally-sourced lead-list tool. New-registration filings are a birth certificate, not a profile. The growth layer stays inside the firm's own data; reaching outside it is where the concept weakens.
•    Not a platform-level micro-targeting engine. JAMM is the strategist, not the media buyer.
•    Not the client relationship additions (satisfaction pulse, tenure display, service expansion tracking). Those are separate small builds over existing Client data, out of scope here, available to pick up after this ships.
•    Not the Best-Client Profile or any intelligence synthesis surface. Andrew's layer, later.
•    No SMS in v1 (see 6.8). No campaign assembler. No cross-firm channel index (structurally cohort-gated, far future).
# 3. Source attribution: the load-bearing design
Where a lead came from is the one piece of data that can never be backfilled. This section is the part of the build that must be right from day one.
## 3.1 Three layers, each capturing what its data source can honestly know
•    Layer 1, channel (the motion): the ReferralSource enum. Small, stable, what cross-firm intelligence will someday compare. The enum ALREADY EXISTS in app/core/enums.py on the Client model; this build extends it and reuses the same taxonomy on the Lead so attribution flows forward on conversion without translation.
•    Layer 2, platform (the where): a source_platform field. AUTO-DERIVED from utm_source whenever the lead arrived through a tracked link; the manual picker is only the fallback door for leads with no link behind them (manual entry, prose replies, walk-ins). A UTM-derived platform is never overwritten by a hand-picked one. Values: facebook, instagram, tiktok, linkedin, youtube, x, google, bing, nextdoor, other. For cold_outreach the same field carries the mechanism: email, phone, dm, direct_mail.
•    Layer 3, tracking capture (the exactly-where): UTM parameters recorded verbatim on the lead whenever it arrives through a link (campaign, placement, ad set). Reel vs feed lives here, captured by machinery, never by memory. Never ask a human for placement-level detail; recall precision is noise.
## 3.2 The extended enum (decided, ordered as displayed in UI)
client_referral, professional_referral, returning_client, google_search, search_ads, social_ads, social_media (organic), website, association_or_community, walk_in, cold_outreach, purchased_book, other, unknown.
•    unknown always renders LAST in any picker so the reader scans real options first.
•    Enum uses native_enum=False per standing rules. Adding values later is cheap; renames are painful; the set above is motion-complete. Note: a new value longer than the current longest may need a one-line length migration; verify at build time.
•    professional_referral is the value that later gains a pointer to an external referral partner record (attorneys, banks, other firms that refer but are not clients). The partner record type is part of THIS build's source taxonomy: a simple per-firm partner entity (name, type, notes) so repeat referrers are trackable, linked from the lead.
•    referring_client_id (already on Client) applies when the referrer IS an existing client: picked from a searchable dropdown of the firm's clients, never typed.
## 3.3 Provenance and precedence
•    Every attribution record carries a provenance value: how we know this. Three values: crm_lead (captured at intake, flows forward), firm_entered, client_reported.
•    Precedence is substitution, never blending: crm_lead beats firm_entered beats client_reported. Lower tiers fill blanks only and never overwrite higher tiers. Any surface using attribution states which tier it used.
## 3.4 Rulings already made elsewhere (context, no build here)
•    Import wizard: NO attribution capture. Imported clients arrive with it blank by design.
•    Manual client creation: the existing optional referral_source field stays optional, unknown last in the list.
•    The client-side portal attribution survey IS in this build (see 4.1).
# 4. The public intake form: the linchpin
This absorbs the old public client intake form roadmap item. It is the surface Layer 3 attribution lands on: when a firm points its ads and website buttons at this page with tracking tags, attribution becomes automatic and exact for every lead that walks the path.
•    A hosted public page per firm, branded like their portal (logo, colors), served through the existing custom portal domain plumbing so it reads as the firm's own website.
•    Reachable as a hosted link AND embeddable on the firm's existing website.
•    Public and unauthenticated, therefore rate limited and spam-protected from day one.
•    Captures name, contact, service interest, timeline/urgency question (filing deadline / IRS notice in hand), optional how-did-you-hear. UTM parameters captured silently.
•    Submission creates the lead, fires the behavioral event, notifies the firm, and auto-enrolls in the nurture preset (trigger T1 on the tree).
## 4.1 Portal attribution survey (in scope)
•    A one-question survey for EXISTING clients whose attribution is blank (imported and legacy books). Rides the portal notification system as a special pinned type: clears only on completion, never on read, and survives mark-all-read.
•    Renders only when attribution is blank; for everyone else the notification never exists. Options list ends with a do-not-remember choice, last so the client scans real options first.
•    Answers write with client_reported provenance: fills blanks only, never overwrites firm-entered or lead-captured attribution.

# 5. One engine, many doors
The email answer buttons, the form, and staff capture are not three systems. They are three faces of one engine. The lead's position in the nurture tree is the single source of truth; every door writes the same structured fields and advances the same walk. The form has no question logic of its own: it asks whatever the tree says is unanswered next. Do not build the form as a separate island.
•    Answer buttons in emails: a question's options render as buttons; each button is a link with the answer baked in, so one tap records structured data and lands the prospect on the form with that question pre-filled. Standard for every question-bearing email (E2 and E5 especially).
•    The form shows ONE question per screen with a progress count (2 of 5). Short, easy, momentum-preserving.
•    Fast path: form completion runs the fit check instantly. On FIT, booking slots render as the form's FINAL step; the calendar never renders before the questions are answered, so the owner always walks into the call briefed. The full form targets about one minute: few questions, easy answers. On NOT FIT, the form ends on the identical warm thank-you (we will be in touch) while owner review runs behind the scenes; the prospect never experiences rejection live. A goal jump only ever skips chase emails that no longer matter; it never skips qualification, because the form IS qualification. The tree's waits are the safety net, not the speed limit.
•    Prose replies remain a valid door: the reply itself fires the engaged branch (a fact), and a staff task captures the fields manually.
# 6. The nurture engine
Purpose-built sequence models; the existing automation rules cannot express stateful multi-step logic. The accompanying reference tree is the v1 preset and the worked example the engine must be able to express in full. Build the engine to the checklist below, then implement the preset exactly as drawn.
## 6.1 Engine capability checklist
•    Triggers: intake form submitted, lead created (enroll toggle), stage change, manual add.
•    Steps: send email; wait fixed duration; wait until event with timeout (reply, click, form answer, booking, staff action); if/else branches, nestable, evaluating structured fields, tags, and event facts.
•    Goal events: a watched event (call_booked) jumps the lead to the goal node from anywhere in the phase, skipping everything between.
•    Loops with mandatory caps and exit conditions (the rebook loop caps at 2). No uncapped loop ever ships.
•    Stop conditions, global: unsubscribe (suppression list, exits forever), converted to Client, staff removes from sequence.
•    Re-enrollment rules per sequence. Preset default: no concurrent duplicate enrollment; re-entry allowed only along drawn paths (drip re-engagement, timing re-entry).
•    Send windows: firm business hours, 8am to 6pm firm-local, configurable.
•    Testing discipline from the GHL world, adopted as a build rule: every branch is tested on its yes path, no path, AND timeout path before the preset ships.
## 6.2 Branches fire on facts, never interpretations
The only signals that route a branch: reply-exists, link-clicked, form-answered, staff-clicked, date-passed. Free text never steers a branch. Machine-reading meaning from text is prohibited in v1; an LLM assist that pre-fills fields for staff confirmation is a possible later enhancer but never routes on its own.
## 6.3 Versioning (hard requirement, not bolt-on-able)
•    Every edit to a sequence creates a new immutable version. Editing never mutates an existing version.
•    Enrollments pin to the version current at enroll time and finish on it. Edits apply to new enrollments only.
## 6.4 Preset lineage
•    Every sequence carries a preset lineage key (which preset it descends from, survives renames and edits; same pattern as the e-sign preset_key fix) plus a modified-from-preset flag, recorded at step level.
•    The intelligence layer consumes lineage, modified flags, and outcomes only. It never parses modification contents. (Andrew has a further intelligence design here; not Ben's concern in this build.)
## 6.5 Inbound reply capture (mandatory machinery)
Wait-until-reply requires JAMM to SEE the reply. Sequence emails go out with a reply-to address that routes back through Postmark inbound to JAMM; the reply attaches to the lead thread and fires the event. Without this, every wait-until-response node silently degrades to a plain timer and the tree rots invisibly. This ships with the engine, not after it.
## 6.6 Deliverability and legal
•    All nurture mail rides a dedicated Postmark marketing/broadcast stream, never the transactional stream that carries invoices, magic links, and portal invites.
•    Marketing email to non-clients requires a working unsubscribe (CAN-SPAM): unsubscribe link in every nurture send, and a suppression list the engine checks before every send.
## 6.7 The system never decides: review-gated external actions
•    Any automated action with external consequences to a specific person is held for human approval. Concretely: the unqualified decline email (R1 on the tree) is HELD; the owner is notified with the answers the lead gave, approves the decline in one click, or overrides the lead back into the sequence.
•    Every dead end notifies the owner with a one-click take-over that pulls the lead into manual mode. The system automates motion; humans make decisions. This is a standing pattern for any future automation touching a prospect or client directly.
## 6.8 SMS: deferred, seam built now
The message step model carries a channel field from day one, value always email in v1. SMS arrives post-launch as a new channel value and sender (its carrier registration, A2P 10DLC, has its own multi-week clock and starts when Andrew says go). No remodel later.
# 7. Pipeline, booking, proposal, conversion
## 7.1 Stages (ratified)
•    identified, contacted, call_booked, proposal, won, lost. Ordered but skippable (a walk-in ready to sign jumps straight to proposal).
•    lost always carries a lost_reason enum captured at the transition: unqualified, unresponsive, chose_competitor, price, timing, other. Filtered-on-purpose (unqualified) never counts against conversion metrics; that distinction is sacred.
•    won is the transition that creates the Client: attribution and provenance flow forward, the pre-client thread and intake answers ride along to the Client record, and the lead exits every sequence.
•    Lost leads are NEVER purged, unqualified especially. A declined lead with its attribution and disqualifying answers intact is a data point about the channel that produced it (if one channel mostly delivers unqualified leads, the acquisition intelligence must be able to see that). Retention is your build; the analysis is Andrew's layer.
## 7.2 Native booking
•    Booking runs on JAMM's own calendar. No external booking tool: an outsourced booking blinds the sensor at the pipeline's most important beat (no lead.call_booked event, no thread).
•    Availability model, firm-configured: per-staff weekly windows, meeting duration, buffer before and after, daily cap. Designed with a seam for external calendar busy-times to subtract from these windows when sync lands.
•    Meeting location injected automatically into the confirmation, the reminder, and the calendar event: per-staff setting, one of video room link (permanent personal room URL from Zoom/Meet/Teams), phone number, or office address. Set once, never manually sent. Unique per-meeting links via the Zoom or Google Calendar APIs are a fast-follow (Meet links ride the calendar sync work; Zoom is an independent connection).
•    Reschedule link in the reminder; a reschedule is not a no-show. No-show recovery loop as drawn, capped at 2.
## 7.3 Lead context everywhere: the lead detail view
•    Build ONE lead detail view as the lead's home: source and platform, form answers, hot flag, full message thread, current tree position, every touch.
•    The calendar event carries a summary card (source, answers, hot flag) and a one-tap link into that view, so the owner walks into every call already briefed. The pipeline, the hot-lead alert, the dead-end notifications, and the R1 review screen all link into the SAME view. Do not build four partial context displays.
## 7.4 Proposal from existing machinery
•    The proposal generates from the firm's engagement letter template for the selected service type, sent unsigned: scope, fee, start date, one clear accept action.
•    DEPENDENCY FLAG: today's engagement letter templates exist only as seed-run data, not as hard-coded system presets. Andrew is hard-coding versioned, lineage-keyed system preset templates (customizable under the same principles as sequences) as his own task. Your proposal step consumes those presets; since proposal is the last build phase there is runway, but coordinate timing at kickoff rather than discovering the gap mid-build.
•    On won, the accepted proposal becomes the e-sign engagement letter through the existing Dropbox Sign flow. Accepted proposal and signed letter are the same document at two stages of life.
## 7.5 Hot leads
Urgency comes from the timeline question on the form (filing deadline / IRS notice) or a staff mark, never inferred from text. Hot fires an immediate owner alert; hot leads should get a human same-day, not just the sequence.
# 8. Data model requirements
Exact table, field, and relationship names are yours within the standing architecture rules. The shapes below are required.
•    Lead: a record distinct from Client. Firm-scoped, UUID pk, timezone-aware timestamps like everything else. Fields include contact info, stage, lost_reason, referral_source (SAME enum as Client), source_platform, referring_client_id, referral_partner_id, structured qualification fields (service_interest, entity_type, revenue_band, urgency), hot flag, provenance, first_response_time.
•    UTM capture: campaign/source/medium/content/term stored verbatim on the lead when it arrives via a tracked link.
•    ReferralPartner: per-firm external referrer entity (name, type, notes).
•    Sequence + SequenceVersion (immutable) + Enrollment (lead, version pin, current step, next action time, stop state). Preset lineage key and step-level modified flags per 6.4.
•    Message steps carry a channel field (email now, SMS later).
•    Availability: per-staff windows, duration, buffers, daily cap. Meeting location per-staff setting.
•    Suppression list checked before every nurture send.
•    Forms: intake form and qualification questions driven by the tree (one engine); answer-button clicks write the same fields as form answers.
•    On conversion: Client gains the attribution, provenance, and a durable link to the lead history so the pre-client record survives.
# 9. Behavioral events and standing rules
## 9.1 Events (service layer only, fire-and-forget, own session)
Every send, reply, click, form answer, branch outcome, stage change, booking, no-show, dead end, and conversion fires a behavioral event carrying the step id and sequence version. Candidate names below; Andrew blesses the final event-type strings BEFORE first deploy because event names freeze forever once a firm is live:
•    lead.created, lead.stage_changed, lead.form_started, lead.form_submitted, lead.answer_button_clicked, lead.email_sent, lead.email_replied, lead.email_clicked, lead.call_booked, lead.call_rescheduled, lead.call_held, lead.call_no_show, lead.proposal_sent, lead.converted, lead.lost (with reason), sequence.enrolled, sequence.step_advanced, sequence.exited, sequence.goal_reached.
## 9.2 Standing rules that apply in full
•    Tenant isolation absolute; RBAC at every endpoint; audit logging on sensitive actions; thin routers; 4 Pydantic schemas per module; PaginatedResponse on list endpoints; SQLAlchemy 2.0 Mapped[] only; Pydantic v2 only; DateTime(timezone=True) explicit on every timestamp; string names in relationship(); path comment atop every file; background tasks own their SessionLocal; native_enum=False; no em dashes anywhere in strings, copy, or comments.
•    Migrations: the six-step procedure, and the lead-model migration specifically is a design document; Andrew reads it at the deploy step with that in mind. Public intake endpoints get rate limiting like the portal's.
# 10. Build sequencing and your degrees of freedom
## 10.1 Sequencing
•    Step 0: read the Intelligence Layer Design Specification v2 (already asked; one hour; unblocks Andrew's Spine which unblocks your Briefing UI later). Also: the Concierge cron pause stays urgent and separate.
•    Phase 1: calendar sync slice against test accounts (dev/test is exempt from Google verification), then SUBMIT the sensitive-scope verification with the demo video so the review clock (roughly 10 days plus back-and-forth) runs while you build everything else. Calendar scopes ride the existing OAuth application from the Gmail/Outlook metadata work.
•    Then: attribution layer + enum extension + intake form; then Lead model + pipeline; then native booking + availability + lead detail view; then the nurture engine + preset; then proposal + conversion handoff. Watch two or three GHL workflow-builder videos before the engine phase, and spend time inside a few established CRMs (HubSpot, Pipedrive, Close, GHL itself) to absorb how pipelines, lead views, and stage boards conventionally look and behave; the spec is complete but seeing the things operated teaches texture, and the UI should speak the dialect firm owners already expect.
## 10.2 Yours to decide
•    All email copy (the tree's email nodes are briefs, not copy), form question wording, UI layout, endpoint shapes, exact table/field names within the standing rules, internal implementation of the engine.
•    Propose the final event-type strings; Andrew blesses before deploy.
# 11. Defaults you build as-written unless Andrew revises at kickoff
•    Phase 1 is four touches ending in a breakup email; timeouts escalate 2, 3, 4, 5 days.
•    Rebook loop cap: 2. Long-term drip cadence: quarterly, with a 90-day wait-or-engage check; drip re-entry lands at Qualification.
•    Business hours default 8am to 6pm firm-local. Booking phase timeout 3 days; proposal follow-ups at 4 then 5 days.
•    Call held / no-show is a one-click staff mark from the task.

The reference tree artifact is part of this contract. Node IDs in the tree are the shared vocabulary for questions (node 22, E5, R1). If anything in this document and the tree ever disagree, flag it before building; do not pick one silently.
https://claude.ai/public/artifacts/99a30239-91a5-4e5f-9742-4dbc94d756a5
