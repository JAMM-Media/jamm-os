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

TASK: Extend the existing ReferralSource enum with the six new values required by the CRM/Acquisition Tracker build contract, in the exact display order specified. Backend only — no frontend picker exists yet to update, and that's intentional (deferred to the intake form build).

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

sed -n '226,236p' app/core/enums.py
grep -n "referral_source\|referring_client_id" app/models/client.py
.venv/bin/alembic heads

Confirm the real current enum matches exactly: client_referral, professional_referral, google_search, social_media, website, association_or_community, walk_in, other — in that order, as a class ReferralSource(str, Enum). Confirm referral_source and referring_client_id exist on Client exactly as currently defined. Confirm the real current alembic head hash — it must match a2b3c4d5e6f7. If it doesn't, stop and report the real hash instead of proceeding.

WHAT THIS IS:

The CRM contract (Section 3.2) requires ReferralSource extended to 14 values total, in this exact display order, since this same enum is reused on the future Lead model so attribution flows forward on conversion without translation:

client_referral, professional_referral, returning_client, google_search, search_ads, social_ads, social_media, website, association_or_community, walk_in, cold_outreach, purchased_book, other, unknown

Six new values: returning_client, search_ads, social_ads, cold_outreach, purchased_book, unknown. unknown must render last in any picker per the contract, which this ordering satisfies since Python enum iteration order follows declaration order.

Column length is already confirmed sufficient: the real production column is VARCHAR(24), sized to the existing longest value (association_or_community, 24 chars). The longest new value (returning_client, 16 chars) fits with no length migration needed. Do not add a length migration.

This task does NOT include: source_platform, provenance, ReferralPartner, or any Lead model field. Those belong to the Lead model per Section 8 of the contract and Lead does not exist yet — building them now would leave them with nothing to attach to. Do not add them.

CHANGE INSTRUCTIONS:

In app/core/enums.py, rewrite the ReferralSource class body to contain exactly the 14 values above, in that exact order, matching the existing string-value-equals-name pattern (e.g. returning_client = "returning_client"). Do not change the class's docstring unless it's factually now incomplete. Do not touch any other enum in this file.

Write a new Alembic migration, down_revision set to a2b3c4d5e6f7, that alters the referralsource enum type to add the six new values. Follow the exact real pattern already used for native_enum=False string-backed enums in this codebase — confirm from the existing e06c341c7b5a migration (add_client_referral_source_and_firm_) what the correct upgrade/downgrade shape is for this pattern, since a VARCHAR-backed enum with native_enum=False is altered differently than a native Postgres ENUM type would be. Do not assume a native-enum ALTER TYPE approach without confirming the real column type first.

VERIFY AFTER ACT:

sed -n '226,244p' app/core/enums.py
.venv/bin/alembic heads
.venv/bin/alembic upgrade head

PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d clients" | grep referral_source

git diff --stat

Paste all real output. Confirm the enum file shows exactly 14 values in the correct order, confirm the migration applied cleanly against the real local database with no errors, and confirm the referral_source column still exists and did not silently change type.

MANUAL VERIFICATION:

**Restart the backend.** Confirm the API still boots cleanly with no startup errors (this enum is imported in app/models/client.py, a broken enum definition would fail at import time). No manual browser check needed since nothing in the UI references this field yet.

GIT:

Do not commit until Ben confirms the backend restarts cleanly and the migration applied without error.