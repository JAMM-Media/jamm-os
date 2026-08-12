# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".
- Never trust file contents shown in VS Code opened against the Windows copy (C:\Users\corby\jamm-os) or Windows File Explorer. Verify all file state via the WSL terminal (cat, ls -la, wc -l) before assuming a file is stale, empty, or correct.
- Generated snapshot files (codebase_snapshot.txt, frontend/frontend_snapshot.txt) are gitignored. Never manually stage, commit, or resurrect them. Regenerate only via ./update_all_snapshots.sh.
- Before the first commit of any session, confirm git config user.email is ben@jammpx.com. Never assume git identity is correct without checking.
- Before writing or modifying anything touching the Concierge agent, read /home/corby/jamm-os/JAMM_PX_Perfect_Assistant_Build.md in full. Every Concierge task should be traceable to something described in that document.
- If a Concierge tool call fails inside the tool-use loop, the failure must surface as a diagnosable logged event, never as a generic deflection presented to the firm owner as if it were a real answer. Check backend logs for "Tool execution failed" before concluding a knowledge gap exists rather than a broken tool call.

---

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Build the public intake form shell — a per-firm, unauthenticated, Turnstile-protected page that captures a prospect's info and creates a Lead with crm_lead provenance. This is the SHELL only: one flat form (name, contact, service interest, freeform "how did you hear"), not the tree-driven one-question-per-screen flow described in the build contract's Section 5 -- that part is explicitly blocked on a nurture tree artifact Ben does not have yet. Do not attempt to build tree-driven question logic, answer-button email wiring, or nurture auto-enrollment in this task.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/models/firm.py | grep -A15 "class Firm"
cat app/crud/firm.py
grep -n "def log_event" app/services/behavioral_log.py
sed -n '1,40p' app/services/behavioral_log.py
grep -rn "class Notification\|NotificationType\|def create_notification" app/models/notification.py app/services/*.py 2>/dev/null | head -20
grep -n "TURNSTILE" .env
grep -n "^import requests\|^import httpx" app/services/*.py | head -5
cat app/schemas/lead.py
cat app/crud/lead.py
find frontend/src/app/portal -maxdepth 2

Paste all real output. Confirm: the real Firm model fields relevant to branding (logo_url, primary_color, or whatever real fields exist -- do not assume field names, read them), the real log_event() call signature so behavioral events are fired correctly rather than guessed, whether a real Notification model/creation pattern exists and what it looks like, confirmation both TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY are present in .env, which HTTP client library is already in use elsewhere in this codebase (for calling Cloudflare's siteverify endpoint server-side), and the real current Lead schema/CRUD shape from tonight's earlier work.

WHAT THIS IS:

Per the CRM/Acquisition Tracker build contract, Section 4. A hosted public page per firm at /intake/{slug} (Firm.slug already exists, confirmed real and populated -- e.g. Riverside Tax & Advisory's slug is "riverside-demo"), reachable with zero authentication, that captures a prospect's info and creates a real Lead.

This endpoint is the FIRST genuinely public, write-capable endpoint in this codebase. No spam protection exists anywhere else to copy -- Cloudflare Turnstile keys are now real and present in .env specifically for this task. Rate limiting DOES have a real precedent: check_email_rate_limit(email, max_requests=3, window_seconds=900), confirmed real and already used identically in app/api/portal.py at lines 170 and 388. Match that exact call shape and those exact numbers for the email-based limit. Also apply the existing @limiter.limit() IP-based decorator pattern from app/core/rate_limit.py on top of it, not instead of it -- this endpoint needs both layers, matching the portal's own auth endpoints which use IP-based @limiter.limit() decorators.

Every lead created through this endpoint uses provenance=LeadProvenance.crm_lead -- this is the ONE place in the codebase that endpoint is allowed to use that value, per the code comment already written in app/api/leads.py during tonight's earlier CRUD task. UTM parameters (utm_campaign, utm_source, utm_medium, utm_content, utm_term) are captured silently from query parameters on the page load and carried through to submission -- never surfaced to the visitor, never asked as a question.

CHANGE INSTRUCTIONS:

1. Backend -- app/api/intake.py, a new public router, prefix "/intake", no auth dependency of any kind on any endpoint in this file:

   GET /intake/{slug}/config -- public, unauthenticated. Looks up the firm by slug via the real existing get_firm_by_slug(). Returns only what a public page needs to render firm branding safely (confirm exact real branding fields from VERIFY BEFORE ACT output -- do not invent field names). Returns 404 if slug doesn't exist. Include TURNSTILE_SITE_KEY in this response (the site key is safe to expose publicly by design -- it's the secret key that must never leave the backend).

   POST /intake/{slug}/submit -- public, unauthenticated. Real request body: name (required), email (required), phone (optional), service_interest (optional freeform string), how_did_you_hear (optional freeform string, stored into Lead.urgency is WRONG -- check the real Lead schema from VERIFY BEFORE ACT and store this into whatever field is actually appropriate, likely a new use of an existing nullable field or flag clearly in a code comment if no clean field exists yet), utm_campaign/utm_source/utm_medium/utm_content/utm_term (all optional, captured from the page not asked of the visitor), and a turnstile_token (required).

   Real submission flow, in order:
   a. Look up firm by slug, 404 if not found.
   b. Verify turnstile_token server-side by POSTing to Cloudflare's real siteverify endpoint (https://challenges.cloudflare.com/turnstile/v0/siteverify) with the real TURNSTILE_SECRET_KEY from settings, the token, and the request's real remote IP. Reject with 400 if verification fails. Do this using whatever HTTP client library is already the real convention in this codebase (confirmed from VERIFY BEFORE ACT), not a newly introduced one.
   c. Apply check_email_rate_limit(email, max_requests=3, window_seconds=900), matching the exact real portal precedent. Reject with 429 if exceeded.
   d. Create the Lead via the real existing create_lead() CRUD function, firm_id from the looked-up firm, provenance=LeadProvenance.crm_lead explicitly. Map name/email/phone/service_interest directly. Map referral_source appropriately if determinable from UTM presence (if utm_source is present, this came through a tracked link -- leave referral_source null and let a human or a future automated pass classify it later; do not guess a ReferralSource value from raw UTM strings in this task, that mapping is a real design decision the contract does not specify and Ben has not made).
   e. Fire a real behavioral event using the real confirmed log_event() signature from VERIFY BEFORE ACT -- event name lead.created (this is the exact string from the contract's own Section 9.1 candidate list, not a task-invented name).
   f. If a real Notification creation pattern was confirmed in VERIFY BEFORE ACT, notify the firm owner that a new lead came in. If no clean existing pattern exists, skip this sub-step entirely and say so plainly in your summary rather than inventing a new notification mechanism in this task.
   g. Return a real success response. No nurture auto-enrollment call -- that does not exist yet.

2. Frontend -- frontend/src/app/intake/[slug]/page.tsx, a fully public page with NO app shell, NO sidebar, NO auth check of any kind -- confirm from the real portal login/magic-link pages (VERIFY BEFORE ACT) what an unauthenticated page's real layout pattern looks like in this codebase, and follow it.

   On load: call GET /intake/{slug}/config. If 404, show a plain "this page doesn't exist" state, not a broken render. Otherwise render the firm's real branding (confirmed fields from VERIFY BEFORE ACT), and silently capture any utm_* query parameters present in the URL into component state -- never render them as visible fields.

   Render ONE flat form: name, email, phone (optional), a short freeform "what can we help with" text field (service_interest), a short freeform "how did you hear about us" text field. Include the real Cloudflare Turnstile widget using the site key from the config response -- use the real Turnstile JS API (https://challenges.cloudflare.com/turnstile/v0/api.js), rendered as a real widget the visitor must complete before submit is enabled.

   On submit: POST to /intake/{slug}/submit with the form fields, captured UTM values, and the real Turnstile token. Show a plain, warm confirmation state on success ("thanks, we'll be in touch") -- per the contract's Section 5, this SAME confirmation state must show regardless of anything about fit or qualification, since qualification logic does not exist in this shell task at all. Show a real, clear error state on failure (rate limited, turnstile failed, firm not found), not a silent failure.

   Do NOT build multi-step/one-question-per-screen UI. Do NOT build a progress indicator. This is explicitly a flat single-screen form for this task -- the tree-driven experience is future work.

3. Register the new intake router in app/main.py, following the real existing include_router pattern and placement convention.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build 2>&1 | tail -20

cd /home/corby/jamm-os
grep -n "include_router(intake_router" app/main.py
git diff --stat

Paste all real output. Confirm a clean frontend build with zero TypeScript errors, confirm the router is actually mounted, confirm the diff only touches files this task should touch.

MANUAL VERIFICATION:

**Restart both the backend and the frontend.** Confirm the backend boots with no import errors.

Then Ben will test this live in an incognito browser window (no session) at localhost:3000/intake/riverside-demo -- confirming the real branding loads, the real Turnstile widget renders and must be completed, a real submission creates a real Lead with provenance=crm_lead (checkable via psql: SELECT name, email, provenance, utm_source FROM leads ORDER BY created_at DESC LIMIT 1;), and that visiting /intake/some-fake-slug-that-does-not-exist shows the plain not-found state rather than a broken page.

GIT:

Do not commit until Ben confirms the live submission in the browser actually created a real Lead row with the correct provenance, verified via real psql output, not just a success toast in the UI.