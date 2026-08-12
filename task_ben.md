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

TASK: Build the Lead CRUD API — service layer, router, and CRUD functions on top of the Lead and ReferralPartner models shipped earlier tonight. This is the layer that enforces provenance precedence, which the schema alone does not protect.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/models/lead.py
cat app/schemas/lead.py
cat app/models/referral_partner.py
cat app/schemas/referral_partner.py
cat app/crud/task.py
cat app/api/tasks.py
cat app/dependencies/roles.py
grep -n "include_router" app/main.py | tail -5

Paste all real output. Confirm the real current shape of everything built tonight before writing anything on top of it -- do not assume the shape described in this task's prose matches the real files without checking, since Claude Code's own prior summary of what it built could differ in some small way from the real file content.

WHAT THIS IS:

Two real problems exist in the current LeadCreate/LeadUpdate schemas that must be fixed at the service layer, not just documented:

PROBLEM 1: LeadCreate currently requires provenance as a caller-supplied field with nothing enforcing which values which callers may set. Per the build contract, provenance describes HOW the system knows a lead's attribution -- crm_lead means the intake form or a tracked link captured it automatically, firm_entered means staff typed it in by hand, client_reported means an existing client answered the portal attribution survey. A staff member manually creating a lead through this API must never be able to claim crm_lead provenance for it -- that would be a false claim about how the data was captured, and future intelligence-layer trust in provenance depends on this being real.

PROBLEM 2: LeadUpdate currently allows provenance to be freely overwritten with no precedence check. Per the contract, precedence is substitution, never blending: crm_lead beats firm_entered beats client_reported. Lower tiers fill blanks only and never overwrite higher tiers. A naive attribute-copy update loop (the pattern Task uses, which is correct for Task since Task has no precedence concept) would let a low-tier update silently stomp a high-tier value already on the lead. This must not be possible through this API.

CHANGE INSTRUCTIONS:

1. In app/crud/lead.py, write CRUD functions following the exact real structure of app/crud/task.py:
   - get_lead_for_firm(db, lead_id, firm_id) -> Lead | None
   - get_leads_for_firm(db, firm_id, stage=None, hot=None) -> query, for use with paginate(), matching get_tasks_for_firm's real filter-building shape
   - create_lead(db, lead_in, firm_id, provenance) -- provenance is a required plain function argument here, NOT read from lead_in. This is what makes problem 1 structurally impossible rather than merely policy: the service layer decides provenance based on WHICH endpoint is calling, never trusts a value the caller embedded in the payload.
   - update_lead_with_precedence(db, lead, update_in, new_provenance) -- this is the real fix for problem 2. Before applying update_in's changes, compare new_provenance's tier against the lead's CURRENT provenance tier using the real precedence order (crm_lead=3, firm_entered=2, client_reported=1, higher number wins). If new_provenance's tier is LOWER than the lead's current tier, only apply fields from update_in that are currently None/blank on the lead -- never overwrite an existing non-null value. If new_provenance's tier is EQUAL OR HIGHER, apply update_in normally (full overwrite of provided fields), and update the lead's provenance field to new_provenance. Write this as a real, readable tier-comparison, not a magic-number one-liner -- define the tier order as a small module-level dict or similar so it's legible six months from now.
   - No delete_lead function. Per the build contract, lost leads are never purged -- a declined lead with its attribution intact is a real data point about the channel that produced it. Do not build a DELETE endpoint or CRUD function for Lead at all.

2. In app/crud/referral_partner.py, standard CRUD (get, list for firm, create, update). ReferralPartner has no provenance concept, no precedence logic needed. A DELETE endpoint IS appropriate here since partners are just contact records, not attribution history -- but confirm no Lead currently references a partner before allowing delete (real FK check, not just relying on ON DELETE SET NULL to silently null out real attribution data without anyone knowing it happened).

3. In app/api/leads.py, build the router following the exact real structure of app/api/tasks.py:
   - POST /leads/ -- creates with provenance=LeadProvenance.crm_lead if the request includes a real signal it came through an automated channel (for now, since the intake form doesn't exist yet, this endpoint is staff-facing only -- use provenance=LeadProvenance.firm_entered unconditionally for every lead created through this endpoint in this task). Leave a clear code comment explaining that a second, separate public/unauthenticated endpoint will be needed for the future intake form, which will pass crm_lead, and that this endpoint intentionally never does. Role: require_staff_or_above, matching Task's create floor.
   - GET /leads/ -- list, PaginatedResponse[LeadOut], filterable by stage and hot, matching list_tasks's real query-param and pagination shape exactly. Role: require_staff_or_above.
   - GET /leads/{lead_id} -- single lead. Role: require_staff_or_above.
   - PATCH /leads/{lead_id} -- calls update_lead_with_precedence, always passing provenance=LeadProvenance.firm_entered (same reasoning as create -- this is a staff-facing endpoint in this task, not the future portal attribution survey which will pass client_reported). Role: require_staff_or_above.
   - No DELETE endpoint.

4. In app/api/referral_partners.py, standard CRUD router: POST, GET list, GET single, PATCH, DELETE (with the real FK check from step 2). Role: require_manager_or_above for create/update/delete, require_staff_or_above for read -- partners are a lighter-weight setup concern than lead data itself.

5. Register both routers in app/main.py, following the exact real pattern of the existing include_router calls -- confirm the real correct placement and prefix/tags convention from the VERIFY BEFORE ACT output rather than guessing.

6. Audit logging: per real precedent (Client logs 'client.updated' on every update, unconditionally, via write_audit_log), add write_audit_log calls for lead.created and lead.updated in the service/CRUD layer, action='lead.created' / 'lead.updated', entity_type='lead', actor_type='staff'. Do NOT add audit logging to ReferralPartner -- Task has no audit logging at all and ReferralPartner is closer to Task's footprint (internal setup data) than Client's (client PII).

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build 2>&1 | tail -5 (only if this task touched anything under frontend/, which it should not -- if this command finds nothing to build against, say so plainly rather than fabricating output)

cd /home/corby/jamm-os
grep -n "def create_lead\|def update_lead_with_precedence" app/crud/lead.py
grep -n "include_router(leads_router\|include_router(referral_partners_router" app/main.py
git diff --stat

Paste all real output. Confirm the precedence function exists with real logic, confirm both routers are actually mounted (a built-but-unmounted router is a silent dead endpoint), confirm the diff only touches the files this task should touch.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot, no import errors. Then, using the Riverside test firm credentials, manually hit the API directly (curl or the FastAPI /docs page) to prove the precedence logic actually works, not just that it compiles:

1. POST a lead with no provenance in the payload (confirm the API ignores any provenance field if sent, and creates with firm_entered regardless).
2. PATCH that lead's phone number. Confirm it updates normally, since firm_entered patching a firm_entered lead is equal-tier.
3. Manually set that lead's provenance to crm_lead directly in the database via psql (simulating what the future intake form would produce), then PATCH the same lead's phone number again through this staff-facing endpoint. Confirm the phone number does NOT change, since firm_entered is lower-tier than the lead's current crm_lead and the field is already non-null -- this is the real proof the precedence logic works, not just that it exists.

Report back plainly what each of the three real API calls returned.

GIT:

Do not commit until Ben confirms all three manual verification steps in step above pass for real.