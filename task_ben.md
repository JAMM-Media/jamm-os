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

TASK: Build real pipeline stage-transition logic for Lead, per the CRM build contract Section 7.1. Two concrete behaviors: (1) transitioning a lead's stage to "lost" requires lost_reason to be set, not merely optional. (2) transitioning a lead's stage to "won" creates a real Client, carrying attribution and provenance forward, and the lead retains a durable link to the Client it became.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/crud/lead.py
cat app/schemas/lead.py
cat app/api/leads.py
cat app/models/lead.py
grep -B2 -A30 "class ClientBase" app/schemas/client.py
grep -n "def create_client" app/crud/client.py
cat app/models/client.py | grep -B3 -A15 "quickbooks_customer_id\|entity_type:"
grep -n "def log_event" app/services/behavioral_log.py

Paste all real output. Confirm the exact real current shape of update_lead_with_precedence and the leads router before modifying either -- this task adds transition logic on top of tonight's earlier work, it does not replace it. Confirm the real create_client() signature and real Client fields available to populate on creation.

WHAT THIS IS:

Per contract Section 7.1: "lost always carries a lost_reason enum captured at the transition... won is the transition that creates the Client: attribution and provenance flow forward, the pre-client thread and intake answers ride along to the Client record, and the lead exits every sequence."

"The lead exits every sequence" is explicitly OUT OF SCOPE for this task -- no sequence/enrollment system exists yet (that's the nurture engine, still blocked on an artifact Ben doesn't have). Do not build any sequence-exit logic. Note this omission plainly in your summary rather than silently skipping it.

"The pre-client thread and intake answers ride along" -- Lead has no message-thread model yet (that's part of the lead detail view, Section 7.3, not built yet either). This task carries forward only what concretely exists on Lead today: name, email, phone, referral_source, referring_client_id, entity_type, service_interest (map to Client.business_description if that's the closest real fit -- confirm from VERIFY BEFORE ACT whether a better field exists, do not force a mismatch). Anything Lead has that Client has no equivalent field for should be explicitly listed as dropped in your summary, not silently discarded without mention.

CHANGE INSTRUCTIONS:

1. In app/models/lead.py, add one new field: converted_client_id, FK to clients.id, ondelete SET NULL, nullable=True. Bare FK only, no relationship() -- matching the exact real reasoning already used twice on this same model (referring_client_id, referral_partner_id): nothing needs to traverse it yet. Write a real Alembic migration for this single column addition. Get the real current alembic head fresh via a live `.venv/bin/alembic heads` call in this task -- do NOT trust any hash mentioned anywhere else in this task's own text or in any prior context, confirm it live, since this exact mistake has happened twice already tonight.

2. In app/crud/lead.py, add a new function transition_lead_stage(db, lead, new_stage, lost_reason=None, current_user_id=None) that is the ONLY correct way to change a lead's stage going forward:
   - If new_stage is LeadStage.lost: raise a real ValueError (caught and converted to a 400 in the router) if lost_reason is None. Set both stage and lost_reason together.
   - If new_stage is LeadStage.won: call a new function convert_lead_to_client(db, lead) (write this in app/crud/lead.py or a new app/services/lead_service.py -- your call which, but be consistent and explain the choice in your summary). This function creates a real Client via the existing create_client(), passing forward: name, email, phone, referral_source, referring_client_id, entity_type from the lead, plus firm_id from the lead itself. Then sets the lead's stage to won and converted_client_id to the new client's real id. Do this inside one real database transaction -- both the Client creation and the Lead update must succeed together or neither should persist; do not leave a lead half-transitioned if Client creation fails partway.
   - For any other stage value: apply normally, no special handling.
   - This function does NOT go through update_lead_with_precedence's provenance-tier logic -- stage transitions are a different concern from attribution field updates, and conflating them would be wrong. Stage and lost_reason are not provenance-gated fields.

3. In app/api/leads.py, add one new endpoint: POST /leads/{lead_id}/transition, taking a small real request body (new_stage: LeadStage, lost_reason: LeadLostReason | None = None), calling transition_lead_stage. Return the updated LeadOut on success, and if the lead was won, also return the new client_id in the response (extend LeadOut or return a small wrapper -- your call, explain which in your summary). Role: require_staff_or_above, matching every other lead-touching endpoint tonight. Return 400 with a clear message if lost is attempted with no lost_reason. Do NOT modify the existing PATCH /leads/{lead_id} endpoint to also handle stage transitions -- keep this as a separate, explicit action endpoint, since a transition is a meaningfully different, more consequential action than a normal field edit and deserves its own clear entry point rather than being buried in a generic PATCH.

4. Fire a real behavioral event on conversion using the real confirmed log_event() signature: event name lead.converted, per the contract's own Section 9.1 candidate list. Also fire lead.lost (with reason) when the lost transition happens, same section, same real signature.

VERIFY AFTER ACT:

.venv/bin/alembic heads
.venv/bin/alembic upgrade head
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d leads" | grep converted_client_id
grep -n "def transition_lead_stage\|def convert_lead_to_client" app/crud/lead.py app/services/lead_service.py 2>/dev/null
grep -n "/transition" app/api/leads.py
git diff --stat

Paste all real output.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot. Then Ben will run a real end-to-end test:

1. Attempt POST /leads/{id}/transition with new_stage=lost and no lost_reason. Confirm a real 400, not a 500 or a silent success.
2. POST the same with new_stage=lost and a real lost_reason. Confirm success, confirm via psql that both stage and lost_reason landed correctly.
3. Create a fresh test lead, POST /leads/{id}/transition with new_stage=won. Confirm the response includes a client_id. Confirm via psql that a real new row exists in clients with the lead's name/email/phone, and that the lead's own row now shows stage=won and converted_client_id pointing at that real client id.

Report back all real psql output for step 3 especially -- this is the step that proves the actual conversion worked, not just that the endpoint returned 200.

GIT:

Do not commit until Ben confirms all three manual steps pass with real evidence, especially the won conversion actually creating a real linked Client row.