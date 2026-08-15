<!-- Created 2026-08-14/15 during a live build session. This document captures the full reasoning behind every item on the priority list, not just the item itself, so context is never lost to a closed chat window. -->

# CRM Build Priority List and Research Findings

## Why this document exists

Everything in this document was worked out live, in conversation, across a single long session. The checklist alone is not enough — a bare list of task names loses the *reasoning* behind why each item is placed where it is, what risk it carries, what was debated about it, and what was ultimately decided and why. This document exists to preserve that reasoning permanently, in a place that survives beyond any one chat window.

Nothing in this document is a locked spec the way the CRM Build Contract addenda are. This is a living priority list, expected to be edited, reordered, and argued with as work progresses.

---

## Part 1: The In-Flight Backend Build Sequence (Native Booking)

This is the active, currently-being-built sequence. It was deliberately sequenced backend-first, frontend last, per an explicit decision made mid-session: five of the seven remaining CRM pieces were backend work, and there was no reason to force a frontend detour into the middle of a backend streak just because it happened to appear next in an earlier, less-thought-through ordering.

### 1. Availability Window model, schema, migration — COMPLETE, committed at `426af69`

Built as pure data-model foundation. One row represents one recurring weekly time block for one staff member (e.g. "Tuesdays 9am to noon"). Fields: `firm_id`, `user_id`, `day_of_week` (0=Monday, matching Python's own `weekday()` convention), `start_time`/`end_time` (true time-of-day storage via `sa.Time()`, not full datetimes, since this is a recurring rule not a specific appointment), `buffer_before_minutes`, `buffer_after_minutes`, `meeting_duration_minutes`, `daily_cap` (nullable, null meaning no cap enforced).

A real, deliberate tradeoff was made and is documented in three places (the model's own docstring, a saved memory entry, and here): `meeting_duration_minutes` and `daily_cap` are logically per-staff-member settings (a person doesn't usually want a different meeting length on different days), but they were stored per-window instead, purely to avoid touching the `users` table and to keep this migration to exactly one new table. The real risk this creates: a staff member with multiple windows could end up with contradicting caps or durations across different windows, with nothing in the database enforcing they agree. This must be resolved — either by moving these fields to `User` or to a new `StaffSchedulingSettings` model — before the booking engine (item 4 below) is built, because that's the point where inconsistent values would actually cause incorrect behavior rather than just sitting unused.

The database itself enforces one hard rule: a `UniqueConstraint` on `(user_id, day_of_week)` makes it structurally impossible for one staff member to have two separate windows for the same day. This is enforced by Postgres, not just application code.

### 2. Availability Window CRUD endpoints — COMPLETE, committed at `48eef23`

Real API endpoints: list all windows in a firm (team visibility), list your own windows, create/update/delete a window. A genuine RBAC assumption was made here, since the contract does not specify who may edit whose windows — only that availability is "firm-configured, per-staff." The assumed rule, stated explicitly in both the router's docstring and the test file: any staff member can *view* every window in the firm (useful for team scheduling visibility), but can only *create, update, or delete their own* windows, unless they are a `firm_owner` or `manager`, who may manage any staff member's windows within the firm. This is a guess, not a confirmed contract requirement, and is flagged loudly as such rather than silently assumed.

A real engineering decision worth recording: the duplicate-day database constraint (from item 1) will, if violated, throw a raw `IntegrityError` from Postgres. The create/update logic specifically inspects the Postgres error code (`23505`, meaning "unique violation") before converting it into a clean, human-readable 409 error message. Other kinds of database errors are deliberately *not* caught and converted — they are allowed to remain loud, unhandled errors, so that a real, different problem is never mislabeled as "you already have a window that day."

Test coverage proved, with real watched red/green cycles: a staff member cannot create a second window for a day they already have one (and the failure mode was proven to go from an ugly raw 500 error to a clean 409 message); tenant isolation holds in every direction (read, update, delete) between two different firms; a staff member cannot modify a colleague's window; a manager or firm owner can.

### 3. Booking model — IN PROGRESS as of this document's creation

A real row representing one actual scheduled meeting: which lead, which staff member, the real start and end time (full timestamps here, unlike the recurring time-of-day-only fields on Availability Window, since this is one specific real event, not a recurring rule), a status field, and a "location snapshot" — a deliberate design decision to record what the meeting location actually was *at the moment of booking* (a video link, a phone number, or an office address), separate from whatever the staff member's location *setting* might later change to. This matters because if a staff member changes their default meeting location next month, a booking made last month should still show the location that was true when it was actually booked, not silently update to reflect a change that happened after the fact.

### 4. Meeting location setting — NOT STARTED

Per-staff setting: video room link, phone number, or office address. Automatically injected into the confirmation email, the reminder, and the calendar event itself, per the contract's explicit language: "set once, never manually sent."

### 5. Slot computation — NOT STARTED

The real math: take a staff member's recurring availability windows, subtract their buffers, subtract anything already counted against their daily cap, subtract whatever's already booked (from item 3), and produce the actual, honest list of open times for a given week.

This step is directly informed by outside research (see Part 3, Finding R1) which materially changed the plan: buffers should NOT be pre-subtracted from the raw availability window ahead of time. Instead, each individual real booking gets its own "protected time window" — buffer-before and buffer-after — computed and checked only once that specific booking exists. An empty calendar shows zero buffer-blocked time anywhere, because there is nothing yet to protect. This also means buffers can legitimately *stack*: if one booking's after-buffer and the next booking's before-buffer land next to each other, the combined blocked time can be larger than either buffer alone. This is expected, documented behavior in real scheduling tools (Calendly and Cal.com both explicitly warn about it), not a bug to engineer around.

The daily cap, per the same research, is implemented as a simple count of already-confirmed bookings for that person on that day, checked *after* slots and buffers are resolved — not woven into the slot-partitioning math itself.

Slot computation should be done fresh, on-demand, every time it's requested — never precomputed and cached as a static list — because availability can change from one second to the next (someone else might claim a slot moments earlier).

### 6. The booking action endpoint — NOT STARTED

The real endpoint a lead actually hits to claim an open slot. On success: creates a real `Booking` row, moves the lead's pipeline stage to `call_booked`, and fires a real event. This step connects directly back into the goal-jump mechanism already built earlier in this session — a booked call is exactly the kind of "something great happened on its own" moment that should let the nurture engine skip any remaining follow-up emails in its sequence, since continuing to nurture someone who already booked would be redundant and possibly annoying.

### 7. Post-call outcome handling — NOT STARTED

This is a real, named rule from the original CRM Build Contract, not an invention: the nurture engine is never allowed to guess how a call actually went. When the scheduled call time passes, the system pauses and presents the firm owner with exactly three options: went well (continue), not a fit (move to long-term drip), or no-show (reschedule branch, explicitly not treated as a rejection).

This reuses the exact pause-and-notify pattern already built and shipped earlier tonight for the reply-pause mechanism — same underlying idea, different trigger (a clock running out instead of a message arriving).

One addition worth remembering when this is actually built, again from outside research (Part 3, Finding R4): the speed of the first follow-up after a no-show matters enormously. Real sales-ops guidance says the highest-leverage recovery window is the first 5 to 15 minutes after a missed call, while the person is statistically still available. The post-call pause-and-notify step should probably fire the moment the scheduled call time passes, not wait for the next slow, periodic tick cycle.

---

## Part 2: Blocked and Parked Items (Not Currently Actionable, With Real Reasons Why)

Every item here was deliberately walked through one at a time, with the actual honest reason it can't move forward right now — not a vague "later," but a specific, named blocker.

### Pipeline UI (lead list and detail screens, including the won-transition confirmation dialog)

**Real finding, confirmed by direct reconnaissance of the codebase, not assumed:** no lead-related frontend screen exists anywhere. No lead list, no lead detail view, no API calls from the frontend to any of the five real lead endpoints that already exist and work on the backend. The sidebar navigation has no mention of leads or a pipeline at all.

**What does exist and is genuinely useful:** a reusable confirmation-dialog component (`useConfirm` hook, backed by `ConfirmModal.tsx`) already used elsewhere in the app (the engagements page), with a built-in "destructive action" red-button mode already available. The actual confirmation dialog for the won-transition is a small addition, roughly ten lines of code — but it currently has nowhere to attach to, because the screen it would live on doesn't exist.

**The honest scope finding:** building the pipeline UI properly is not a small addition. The contract describes the lead detail view as a major, unified surface — source and attribution, form answers, the hot-lead flag, the full message thread, current position in the nurture tree, every touch — and explicitly warns against building "four partial context displays" instead of one real one. This is a multi-day frontend feature requiring real design thinking (table view or drag-and-drop kanban board, what belongs on a lead card), not something to build sight-unseen at 1am after nine other verified builds already landed in the same session.

**Decision made:** defer the full pipeline UI to its own dedicated session. In the meantime, prioritize finishing the backend booking sequence (Part 1), since backend work in this session has repeatedly proven well-suited to this pace and doesn't carry the same "needs real design thought" risk.

### `delete_engagement` has no guard — a real, already-known data-loss bug

Found while searching project knowledge for something unrelated (booking-model context). Documented in the project's own Consolidated Roadmap file: deleting an engagement does not check whether it has documents, time entries, or invoices attached before deleting. The cascade permanently destroys real client tax documents. Worse: the event log still records `engagement.archived`, even though the true outcome was permanent destruction, not archiving — meaning the permanent audit record itself misrepresents what actually happened.

This is unrelated to the CRM/booking work but is real and severe. The roadmap document itself says this should ship before any real firm touches the product, and describes the fix as small — a guard in the service layer, matching an existing pattern already used for invoices, requiring no migration.

**Decision made:** placed in the priority list based on severity, not based on where it falls in the natural CRM sequence. Not yet built. Whether it jumps the queue ahead of the remaining booking steps is explicitly left as an open decision, not resolved in this document.

### Scheduler multi-worker safety

**The real finding, from outside research (Part 3, Finding R2):** the nurture engine's tick loop, which is live in production right now, is protected by a single `fcntl` file lock. Research confirmed this is the correct, commonly-recommended pattern — but only for a single-worker deployment. If production ever runs more than one Gunicorn worker process (common in real production deployments for handling concurrent traffic), each worker would independently start its own scheduler instance, and every scheduled job would fire once *per worker* — meaning the exact same nurture email could be sent multiple times to a real lead. This would reintroduce, through an entirely different mechanism, precisely the duplicate-send failure that the write-then-send design (built earlier this session) was specifically created to prevent.

**A related, smaller finding:** APScheduler's default job store is in-memory only, meaning any scheduled job is lost entirely on every restart, unless a persistent store is explicitly configured. Not judged to be an immediate risk, since the actual state that matters (which enrollment is due for what, and when) lives safely in JAMM's own database tables, not inside APScheduler's internal memory — but worth remembering if anything is ever built that depends on APScheduler itself retaining state across a restart.

**Action taken:** a direct question was sent to Andrew asking how many Gunicorn workers production currently runs. This is judged the single most time-sensitive item on this entire list, because if the answer is "more than one," this is not a someday problem — it is a live risk in production right now.

### Gmail scope console removal

Real, split, two-sided task. Andrew is removing the Gmail scopes (`gmail.readonly`, `gmail.send`) from the backend's OAuth request code, as part of descoping the app from Google's expensive "Restricted" review tier down to the cheaper, faster "Sensitive" tier (calendar-only). The other half — removing the same scope declarations from the actual Google Cloud Console consent screen — requires a real, manual browser action logged into Google's own website, which only Ben can perform, since he holds the relevant Cloud Console role (confirmed: OAuth Config Editor and Viewer on the JAMM PX project).

**Decision made:** the two halves must land together, not separately. If the console is changed before the backend code, or vice versa, the two would briefly disagree about what scopes are actually being requested. A message was sent to Andrew asking specifically how he wants this sequenced. Paused pending his reply.

### Test database stability (transaction-rollback instead of TRUNCATE)

**Directly tied to the worst hours of this entire session.** The test suite's cleanup mechanism (`clean_db` in `tests/conftest.py`) uses `TRUNCATE` after every single test, which requires an exclusive lock across every table it touches — a lock so strong that even a single leftover idle connection is enough to block everything behind it. This was the root structural cause of two separate real incidents in this session: a 56-minute freeze caused by one orphaned connection holding a lock, and a genuine Postgres deadlock caused by two concurrent test runs both trying to `TRUNCATE` the same tables in a different order.

**The research finding (Part 3, Finding R1):** wrapping each test in its own database transaction and rolling it back at the end, instead of truncating, avoids this entire class of problem structurally. Nothing is ever actually, permanently written, so there is nothing to lock and nothing to truncate. Real-world reports cited in the research describe this as roughly 80 times faster than the truncate-based approach, and it removes the possibility of the specific deadlock pattern seen tonight entirely, not just makes it less likely. A companion fix — a Postgres advisory lock acquired at the start of a test session — would have automatically caught the incident tonight where six separate pytest processes were accidentally left running at once, rather than requiring a manual `ps aux` check to discover it.

**Decision made:** this is not something to unilaterally rewrite mid-session. `tests/conftest.py` is shared infrastructure that Andrew's own tests run through as much as Ben's. This is a "bring it to him as a real, well-supported recommendation" item, not a "just go fix it" item, despite how directly it explains tonight's worst hours.

### Notification taxonomy

The underlying mechanism — a real notification firing when a lead replies, with the enrollment pausing at the same moment — was built and shipped earlier this session. What remains undecided is the full menu of every situation that should trigger a notification, and for each one, whether it should be "loud" (interrupt the firm owner immediately) or "quiet" (a note to review later, not urgent).

Andrew's own email said explicitly that he would rule on the final taxonomy once the underlying mechanism existed — it now does. Ben was asked directly whether he wanted to make this decision himself instead, since nothing about it technically requires backend access or is locked to Andrew alone; it is a plain judgment call either co-founder could make. Ben's explicit decision: leave it parked at the very end of the list for now, rather than deciding it himself or coordinating with Andrew on it tonight, specifically to avoid the risk of both of them independently reaching different conclusions and creating friction later.

---

## Part 3: Research Findings (Perplexity Deep Research), In Full, With Devil's Advocate Reasoning

Four separate Deep Research queries were run this session, each explicitly identified as requiring Deep Research mode rather than quick search, because each one asked for synthesis and comparison across multiple real sources rather than a single fact lookup.

### Finding R1 — Test Database Stability

**What was asked:** best practices for preventing deadlocks and stale schema state in a pytest suite sharing one Postgres database, specifically comparing transaction-rollback cleanup against TRUNCATE-based cleanup.

**What came back, in full:** TRUNCATE requires an ACCESS EXCLUSIVE lock on every table it touches, conflicting with virtually any other lock held by any concurrent session, including simple reads — making it a structural deadlock risk under any concurrency at all. Transaction-rollback, by contrast, only ever releases locks the test itself acquired, and requires no table-level exclusive lock whatsoever. Real-world reports cited an 80x-plus speedup switching from truncate-based to rollback-based cleanup. The standard implementation is SQLAlchemy's documented pattern of binding a test's session to an outer transaction the test code can't see, using `join_transaction_mode="create_savepoint"` so that any `commit()` inside test code becomes a nested savepoint release rather than a real commit, with the entire outer transaction rolled back at teardown. The one case where TRUNCATE remains the right tool: tests that specifically need to exercise real cross-connection commit behavior, since an uncommitted outer transaction is invisible to any other database connection.

For preventing accidental concurrent test-suite invocations specifically, the research recommended PostgreSQL advisory locks over file locks, because advisory locks are visible database-wide (working correctly even across separate machines or CI runners hitting the same database), whereas a file lock only protects processes sharing the same filesystem.

Several tools were named as offering full per-run database isolation instead of managing a shared database at all: `pytest-postgresql` (spins up an ephemeral Postgres instance or clones a pre-migrated template database per test), `testcontainers` (a disposable containerized Postgres instance per run), and `pgsql-test` (per-test UUID-named databases combined with savepoint rollback).

**Devil's advocate applied:** the appeal of this fix is obvious, given it's the direct explanation for the worst hours of tonight's session. But the honest caution here is that `tests/conftest.py` is not solely owned by this session's work — it is shared infrastructure that Andrew's own test suite runs through as well. A structural rewrite of core test-isolation behavior, however well-supported by outside research, is a different category of change than anything else built tonight, and changing it unilaterally, without his input, risks silently altering how his own tests behave. This is why the decision was made to treat this as a strong, well-evidenced recommendation to bring to him, not something to implement mid-session.

**My opinion:** this is the single most valuable piece of outside research from the whole session, in terms of preventing future pain, precisely because it explains a real, already-experienced failure with a specific, well-documented, low-complexity fix (the research itself calls the rollback pattern "the highest-leverage, lowest-complexity fix for both deadlocks and speed"). I would prioritize raising this with Andrew relatively soon, not because anything is on fire right now, but because the exact failure mode it prevents has already cost real time twice in one session, and the fix is proven, not speculative.

### Finding R2 — APScheduler and Multi-Worker Production Safety

**What was asked:** known pitfalls of running APScheduler inside a FastAPI app deployed with multiple Gunicorn workers, whether a simple `fcntl` file lock is a reliable production pattern, what's commonly used instead, and known issues with job loss or double-firing after deploys.

**What came back, in full:** if each Gunicorn worker independently starts its own scheduler instance, every scheduled job fires once per worker, not once total — described by the research as a widely reported, confirmed issue, not an edge case, with the APScheduler maintainers themselves acknowledging that multiple uncoordinated scheduler instances "will lead to incorrect scheduler behavior like duplicate execution or the scheduler missing jobs entirely." A real cited postmortem traced a mysterious CPU spike directly to four Gunicorn workers each independently firing the same scheduled job.

A single-host `fcntl.flock`-based lockfile (the pattern already built and shipped tonight) was confirmed as a commonly recommended, reasonably reliable approach — but explicitly scoped to a single host only. It provides no protection whatsoever across multiple containers, pods, or separate hosts. It can also interact awkwardly with Gunicorn's `--preload` flag, since preloading changes when and how the application code (and therefore any lock-acquisition logic tied to import time) actually runs relative to the worker fork.

What production teams commonly use instead, in rough order of frequency: a fully separate, dedicated scheduler process running entirely outside the normal web-worker pool (described as "the most robust pattern" and "what most production setups use"); a distributed lock via Postgres advisory locks or Redis, extending the same file-lock idea to work across multiple hosts; or switching to a tool built for genuinely distributed execution, most commonly Celery with Celery Beat, where a single beat process emits tasks that any number of independent workers can pick up exactly once.

Separately, but related: APScheduler's default job store is in-memory only, so a restart (which every deploy causes) wipes every scheduled job unless a persistent store like `SQLAlchemyJobStore` is explicitly configured. Re-adding jobs on every startup without a stable, explicit `id` and `replace_existing=True` causes duplicate job definitions to silently accumulate in a persistent store across repeated deploys.

**Devil's advocate applied:** it would be easy to treat this as an urgent five-alarm problem and rush a fix. The honest, calmer read: nothing has actually gone wrong yet. The current lock is not wrong — it is correctly scoped for exactly the deployment shape it's currently protecting (a single host). The real open question is a fact only Andrew knows and controls: how many workers does production actually run. Building a distributed-lock solution speculatively, before knowing whether it's even needed, would be solving a problem that may not exist yet, at the cost of real complexity added to a system that's currently working correctly.

**My opinion:** this is the single most time-sensitive finding from tonight's research, specifically because it's about something already live in production, not something being planned. It is the only one of the four research threads that produced an immediate, direct message to Andrew rather than being simply parked, because it is the only one where the honest answer to "does this matter right now" depends entirely on a fact only he has.

### Finding R3 — B2B CRM Duplicate Detection, Lead Routing, and No-Show Recovery

**What was asked:** standard approaches in B2B service-business CRMs to duplicate lead detection, automatic lead routing and assignment, and no-show recovery specifically.

**What came back, in full:** established CRMs (HubSpot, Salesforce, Dynamics 365) primarily match on email as the anchor identifier for duplicate detection, layering fuzzy matching on phone and name on top, since email is the most consistent unique field. Native out-of-the-box matching in these tools is limited and reportedly misses 30-40% of real-world duplicates involving nicknames, typos, or formatting differences. The standard response to a detected duplicate is to flag it for human review with a confidence score, not to auto-merge; auto-merge is reserved for high-confidence exact matches, typically an exact email match alone, since fuzzy matches on name or phone are considered too error-prone to merge without a human checking first. The recommended architecture layers real-time matching at the moment a lead is created with a periodic scheduled batch pass to catch anything that slipped through initially.

For lead routing, three algorithms dominate: round robin (simple sequential cycling through a fixed rep list), workload/load-balanced (routing based on each rep's current count of open leads relative to a configured cap), and territory/specialty-based (matching against geography, industry, or named-account rules). The more sophisticated production pattern layers these sequentially rather than picking one: check for a duplicate first (so a returning lead routes back to whoever already has the relationship), then match by territory or specialty, then balance by current workload, then weight by lead-quality signals toward more experienced reps. This layered approach is explicitly preferred over bare round-robin, since round-robin alone ignores account history and rep specialization entirely.

For no-show recovery specifically, a no-show is treated as fundamentally distinct from an explicit rejection or a normal "lost" outcome — the stated reasoning is that a no-show reflects a scheduling or timing failure, not a signal about product fit or interest. The recommended recovery structure: react fast, ideally within 5 to 15 minutes of the missed meeting, since the prospect is statistically still available in that window and this is described as the single highest-leverage recovery lever available; use a short, multi-channel cadence (3 to 5 touches across 7 to 10 business days, deliberately alternating channels rather than repeating the same one); keep the tone neutral and assume good faith rather than guilt-tripping, offering concrete new time options rather than a vague "let's talk" ask; log the no-show as its own distinct sub-stage in the CRM rather than folding it into a generic pipeline stage, so no-show recovery rates can be tracked separately from win/loss rates; and if the full recovery sequence gets no response, move the deal to inactive with a short, low-pressure closing message, but add the contact to a long-term nurture list rather than discarding them entirely, since a no-show prospect is considered more likely to resurface later than someone who explicitly declined.

**Devil's advocate applied, per item:**

*Duplicate detection:* the real danger here is not building the feature, it's what happens on a false positive. If the system incorrectly merges two genuinely different people who happen to share a common name, or silently blocks a real, new, unrelated inquiry from someone who contacted the firm about something else months earlier, that outcome is actively worse than doing nothing at all. If this is ever built, it must never make an irreversible decision unilaterally — it should only ever surface a suggestion for a human to confirm, with true auto-merge reserved strictly for an exact email match, matching what the research itself recommends as the industry-safe pattern.

*Lead routing:* this deserves real scrutiny before being treated as an obvious win. The research describes a feature built to solve workload balancing across a team of sales reps. JAMM's actual target customer, per its own product definition, is firms of 2 to 40 staff. A small firm's owner very plausibly wants to personally see and triage every single incoming lead rather than have software silently assign it to someone. Building this risks solving a problem that may not exist for most of JAMM's real, near-term customers, and risks removing a firm owner's instinct to stay personally close to new business. This caution was raised directly; Ben's explicit decision, after hearing it, was to keep the feature on the list anyway rather than demote it, which is recorded here as his considered choice, not an oversight.

*No-show recovery:* this one required the least devil's advocacy, since it turned out to independently confirm a decision Andrew had already made on his own, before this research was ever run — his ruling that a no-show is a scheduling failure, not a rejection, and must not be dripped like one, matches the real industry-standard approach almost exactly. The one genuinely new addition worth carrying forward is the emphasis on speed: the post-call pause-and-notify step (Part 1, item 7) should likely fire immediately when the scheduled time passes, not wait for the next periodic tick.

**My opinion:** duplicate detection and no-show handling are both solid, low-controversy additions to the eventual roadmap. Lead routing is the one genuine judgment call in this set — reasonable people could land on either side, and it was surfaced honestly rather than either silently included or silently cut.

### Finding R4 — Accounting-Specific CRM Feature Gaps

**What was asked:** a broad sweep for structural feature gaps specific to accounting, tax, and bookkeeping CRMs (not generic sales CRMs), explicitly checking proposal-to-engagement handoff, lead-source ROI reporting, referral-partner tracking, seasonal/capacity-based intake, lost-reason analysis, and real user-reported pain points from reviews.

**What came back, in full, by sub-topic:**

*Proposal-to-engagement handoff:* every named competitor treats "proposal signed" as an automated trigger, not a manual step. Practice Ignition automatically creates a structured job from a template the moment a client accepts and pays; Karbon has "Client Tasks" that automatically fire the moment a work item is created, plus a documented five-phase client lifecycle with staff-assignment triggers baked into each transition; TaxDome pairs this with a structured intake questionnaire delivered through the client portal immediately after signing; Financial Cents' lead-tracking template ends with signed engagement letter, then a thank-you, then automatic movement into a formal onboarding checklist template.

*Lead-source ROI reporting:* found to be genuinely shallow across every named competitor. Tools capture source as a simple tag or dropdown and let a user manually filter by it, but none of the researched tools (Karbon, TaxDome, Canopy, Financial Cents, Jetpack Workflow, Content Snare, Practice Ignition) ship a native dashboard actually calculating conversion rate or revenue by source. This functionality, where it exists at all, is typically imported from separate marketing-automation tools or built manually by the firm itself.

*Referral partner tracking:* found to be a genuinely underserved area across every named mainstream tool, but with a mature standard already established in adjacent partner-relationship-management tooling built specifically for accountants. The core distinction: a "lead source" is just a channel tag, while a "referral partner" is a real relationship with its own scorecard and, often, real compliance obligations. Purpose-built accounting referral tools track every introduction from a named partner through to outcome, generate compliance disclosure letters, and capture e-signature consent. The AICPA Code of Professional Conduct was cited as imposing hard, specific constraints: referral fees or commissions cannot be received on attest clients at all, and any referral fee arrangement that is allowed must be disclosed in writing with documented client consent retained. The standard scorecard metrics that specialized referral tools converge on: referral volume sent and received, average client value per referral, conversion rate from referral to signed engagement, a client quality score, and a reciprocity balance tracking whether referrals genuinely flow in both directions between partners.

*Seasonal and capacity-based intake:* found to be a well-documented real pain point industry-wide, but with no established automated solution even among the named competitors. The typical real-world response combines tagging leads by season or cohort, offering different service tiers with different guaranteed turnaround times tied to price, and a firm manually tracking their own utilization percentage, switching to a waitlist message once a self-defined capacity threshold is crossed. True automated, capacity-based intake gating inside the software itself was explicitly described as not being a common built-in feature anywhere in this category.

*Lost-reason analysis:* a single required dropdown field for lost reason is common and considered baseline best practice in generic B2B CRMs, but the research surfaced a more rigorous emerging standard: self-reported lost reasons from the losing side are unreliable, since one cited analysis found buyer-reported and seller-reported reasons for the same lost deal align only about 15% of the time. The recommended fix is a layered taxonomy rather than one flat field: a required primary category, a more specific sub-category within it, the name of a competitor if applicable, a free-text narrative note, and the pipeline stage the deal was lost at. Best practice caps the primary category list at 6 to 8 options, since a longer list causes people to default to whichever option happens to be listed first, and treats a growing "Other" bucket (over roughly 15% of total losses) as a signal that the taxonomy itself is missing a real category. None of the named accounting-specific competitors were found to ship a dedicated lost-reason analytics feature at all — this pattern comes from general B2B sales-operations practice, not from this specific industry.

*Real user-reported pain points,* drawn from G2, Capterra, and Reddit discussion: a consistently steep learning curve and long setup time across multiple named tools; fragmented communication forcing some firms to run two tools in parallel just to get adequate email handling; the CRM layer itself being described by actual users as an afterthought bolted onto a document-workflow-focused core product, with one specific review citing an inability to even see all clients in one place to identify upsell opportunities; billing and invoicing friction, including complaints about inability to run basic accounts-receivable reports and "nickel and diming" from modular, per-feature add-on pricing; slow, gated vendor-side onboarding requiring a sales demo and a one-to-two-week wait before a firm can even begin setup; and inconsistent search functionality across the workspace in more than one named tool.

**Devil's advocate applied, per item:**

*Proposal-to-engagement handoff:* low risk to add, since it extends logic that already exists and already works correctly (the `won`-transition event firing already creates a real client record). The only realistic failure mode is a poorly worded checklist item, which is a cosmetic problem, not a dangerous one.

*Lead-source ROI dashboard:* similarly low risk, since it is pure reporting on data JAMM already captures in full (`referral_source`, `source_platform`, and UTM parameters are already stored on every lead). The worst realistic outcome is a report displaying an incorrect number, which is embarrassing and easy to catch, not dangerous.

*Lost-reason reporting dashboard:* same reasoning as the ROI dashboard. Worth noting explicitly: JAMM's existing `LeadLostReason` field is already a required, structured enum, not free text — meaning JAMM already clears the bar the research itself describes as current best practice. The only real gap is that nothing yet reports on the patterns within that already-good data.

*Referral partner scorecard:* the tracking half of this (volume, conversion rate, average deal value, reciprocity) is low-risk and genuinely differentiating, since the research found literally no named competitor offers this natively, and JAMM already has the foundational `ReferralPartner` model and `referral_partner_id` field on `Lead` built earlier this session to build on top of.

*Referral fee calculation and payout:* this is the one item across the entire session judged to carry meaningfully higher risk than everything else on the list, and it was deliberately separated out from the scorecard as its own distinct line item rather than bundled together. If JAMM's software ever incorrectly calculated who is owed a referral payment — misclassifying an attest client as eligible when the AICPA rules forbid it, or simply containing a calculation bug — the consequence is not a UI annoyance, it is a real accounting firm potentially violating their own professional conduct rules because the software told them a number was correct. There is also a genuine, separate strategic question buried inside this feature: does JAMM actually want to be in the business of calculating and tracking real money owed between parties, given the compliance liability that comes with it, independent of whether it could be built well. Explicit decision: this should not be built speculatively. It requires a real strategic conversation with Andrew first, careful compliance-aware design second, and code only third, in that order.

*Duplicate lead detection and capacity-based intake gating:* both already covered under Finding R3 and this section respectively, with the same caution applied — flag-for-human-review only for duplicates, and for capacity gating specifically, the research's own honest admission that no established tool solves this well yet means any first attempt is unproven territory; if built, it should surface a warning for a human to act on rather than ever auto-pausing lead intake on its own, since the realistic cost of a bug here is a firm silently losing real incoming business without anyone noticing until real revenue was already gone.

*User-reported pain points:* not an actionable build item, but worth preserving as directional validation. One specific complaint — a real user describing a competitor's CRM layer as feeling like "an afterthought" bolted onto the rest of the product — stands out as a direct, if accidental, validation of JAMM's own foundational design principle from the very start of this project: that the CRM and intelligence layer are meant to be central to the product, not an add-on.

**My opinion:** this was the single richest research thread of the night. Two items (proposal handoff, lost-reason reporting) are near-zero-risk extensions of things already built. Two items (lead-source ROI, referral scorecard) are near-zero-risk new reports on data already being captured. One item (referral fee payout) is a real strategic and compliance question that deserves to be treated with real weight, not built casually. And the capacity-gating and duplicate-detection items are genuine gaps worth having on the roadmap, but both carry a real, specific failure mode that must shape how they're eventually built, not just whether they get built.

---

## Part 4: The Full Priority List, In Order, As It Currently Stands

1. Booking model + migration — in progress
2. Meeting location setting
3. Slot computation
4. The booking action endpoint
5. Post-call outcome handling
6. `delete_engagement` guard (real data-loss bug, placed here by severity, not build-sequence order)
7. Scheduler multi-worker safety (blocked on Andrew's reply about production worker count)
8. Gmail scope console removal (blocked on Andrew's sequencing answer)
9. Pipeline UI, including the won-transition confirmation dialog (its own dedicated session)
10. Booking-facing frontend UI (after backend booking work is complete)
11. Test database stability fix, transaction-rollback instead of TRUNCATE (needs Andrew's buy-in, touches shared infrastructure)
12. Onboarding checklist + intake questionnaire auto-triggered on `won`
13. Referral partner scorecard (tracking only)
13a. Referral fee calculation and payout — explicitly not to be built speculatively; strategic and compliance conversation with Andrew required first
14. Lead source ROI dashboard
15. Lost-reason reporting dashboard
16. Duplicate lead detection — flag-for-human-review only, auto-merge restricted to exact email match
17. Automatic lead routing/assignment — kept in the list at Ben's explicit direction, despite a real, raised caution that it may be better suited to larger firms than JAMM's near-term 2-to-40-staff target customer
18. Capacity-based intake gating — no established industry pattern exists to copy; if built, must require explicit human confirmation to activate, never auto-pause lead intake unilaterally
19. Notification taxonomy — lowest priority, parked deliberately, either co-founder's call whenever it's revisited
