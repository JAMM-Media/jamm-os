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

TASK 5 OF N: Standard tenant-isolation and RBAC test coverage for every new authenticated CRM endpoint, per Andrew's Step 5 instruction. Scope: app/api/leads.py and app/api/referral_partners.py only. The other new modules from tonight (Sequence, Step, StepEdge, SequenceGoal, Enrollment, LeadMessage) have no API router at all, by deliberate design in their original build tasks, so RBAC/tenant testing does not apply to them. The three public endpoints (intake, postmark_inbound, unsubscribe) already received tenant-isolation coverage in Step 2 and have no RBAC to test since they are deliberately unauthenticated.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/api/leads.py
cat app/api/referral_partners.py
sed -n '1,60p' tests/conftest.py
sed -n '150,300p' tests/conftest.py
cat tests/test_tasks.py

Paste all real output. Confirm the exact real role requirement on every single endpoint in both files (confirmed already: leads.py is require_staff_or_above throughout; referral_partners.py reads are require_staff_or_above, writes are require_manager_or_above). Confirm the real firm_a_owner, firm_a_staff, and firm_b_owner fixture shapes exactly as they exist today, and read the full real test_tasks.py file as the closest existing real precedent for both RBAC and tenant-isolation test structure in this codebase, since both new test files in this task should match its real conventions rather than invent new ones.

WHAT THIS IS:

Per Andrew's Step 5 instruction: a tenant isolation test proving Firm A cannot read or write Firm B data through any endpoint, and RBAC tests confirming each endpoint rejects roles below its required level, for every new module. Applied here to the two real routers that actually have authenticated endpoints.

CHANGE INSTRUCTIONS:

Create tests/test_leads_rbac_and_tenant_isolation.py:

1. RBAC: for each of the five real endpoints on leads.py (POST /leads/, GET /leads/, GET /leads/{id}, PATCH /leads/{id}, POST /leads/{id}/transition), confirm a client_portal_user role is rejected with 403, following the exact real pattern from test_tasks.py's test_client_cannot_list_tasks (real user creation via the users endpoint or direct model creation matching that file's real approach, real login, real token, real request, real 403 assertion). staff, manager, and firm_owner should all succeed (require_staff_or_above accepts all three), confirm this for at least the list and create endpoints using the real firm_a_staff fixture directly (no need to create a portal user by hand for the positive case, the fixture already exists).

2. Tenant isolation, for EACH endpoint, not just one: using firm_a_owner and firm_b_owner fixtures, create a real Lead under Firm A, then attempt to GET/PATCH/transition it using Firm B's real auth headers. Assert every such attempt returns 404 (not 403, matching the real documented security reasoning already used elsewhere in this codebase for cross-tenant lookups: returning 404 instead of 403 prevents an attacker from confirming a record's existence across tenants, confirm this is the real actual behavior from VERIFY BEFORE ACT rather than assuming it). Also confirm GET /leads/ (list) run as Firm B never includes any Firm A lead in its results, using a real response-body assertion, not just a status code check.

Create tests/test_referral_partners_rbac_and_tenant_isolation.py:

3. RBAC: confirm firm_a_staff (staff role) gets 403 on the three manager-only endpoints (create, update, delete), using the real firm_a_staff fixture. Confirm firm_a_staff succeeds on the two staff-or-above read endpoints (list, get single). Confirm firm_a_owner (satisfies manager-or-above) succeeds on all five.

4. Tenant isolation: create a real ReferralPartner under Firm A, attempt to read/update/delete it as Firm B, assert the real correct rejection status for each (confirm from VERIFY BEFORE ACT whether this module uses 404 or 403 for cross-tenant access, do not assume it matches leads.py without checking the real code). Confirm list as Firm B never includes Firm A's partner.

5. Real test of the active-lead-before-delete check built earlier tonight: attempt to delete a ReferralPartner that has a real Lead referencing it via referral_partner_id. Confirm the real documented 409 response, using a real created Lead and real created ReferralPartner, not a mock.

TEST DISCIPLINE:

Pick ONE test from this task, the leads.py cross-tenant GET returning 404, as this task's real guard test. It must be watched to fail: temporarily remove or bypass the firm_id filter in the relevant real lookup function in app/crud/lead.py (confirm the exact real function and line from VERIFY BEFORE ACT before editing), run the specific test, confirm it goes genuinely red (likely showing a 200 with Firm A's real data returned to a Firm B request, which is the real breach this guards against), restore the real code, re-run to confirm green, run git diff to confirm the working tree is clean. Report the real before and after output in your summary. Ben will independently re-run this exact cycle himself regardless of what is reported.

Never weaken an assertion to make a test pass. If any test in this task exposes a real defect in the already-shipped code, stop, do not modify the test to accommodate the defect, and report the defect plainly as a finding instead.

Tests create their own firms, users, leads, and partners, and must not depend on seed data or test ordering.

No em dashes anywhere in any test file, string, comment, or test name.

VERIFY AFTER ACT:

.venv/bin/pytest tests/test_leads_rbac_and_tenant_isolation.py tests/test_referral_partners_rbac_and_tenant_isolation.py -v 2>&1 | tail -100

Paste the real, full output of both new files running in isolation.

Then:

.venv/bin/pytest > /tmp/pytest_output_step5.txt 2>&1
echo "REAL EXIT CODE: $?"
tail -40 /tmp/pytest_output_step5.txt

Paste all real output. Confirm the real new test count and that the only failures present are the same 9 pre-existing Stripe failures.

MANUAL VERIFICATION:

Ben will independently re-run the real guard-test red/green cycle himself, live, same as every prior guard test tonight, before treating this as complete.

GIT:

Do not commit until Ben confirms the real red/green cycle output he has watched directly, plus the real full suite output.