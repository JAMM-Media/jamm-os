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

# Section 3 - The task

TASK: Build real multi-client batch drafting, review each, send in sequence

USE: Fable 5

VERIFY BEFORE ACT:
grep -n "function parseDraftFromResponse" -A 40 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "MULTIPLE QUALIFYING CLIENTS" -A 15 /home/corby/jamm-os/app/api/concierge/prompts.py
grep -n "msg.draft" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "draft?:" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm all match what is described below. Read every single place msg.draft is referenced in the file in full before changing anything, since this task changes that field from a single object to an array and every read site needs to be updated consistently, not just the ones that are obvious.

WHAT THIS IS:

Currently, when multiple clients qualify for a draft, the model is correctly required to ask which single client the firm owner means, via the OPTIONS marker, and only ever produces one draft once a single client is identified. This is safe and already working. What is missing is a real path for when the firm owner explicitly wants drafts for all of the qualifying clients at once, not just one at a time. Right now there is no way to get more than one draft in a single response at all.

The per-draft client resolution mechanism already exists and already works correctly: each draft block already carries its own CLIENT line, used by the Open to send handler to resolve which real client record to navigate to. This existing mechanism is what makes batch drafting tractable without rebuilding client resolution from scratch, since each draft in a batch can carry its own CLIENT line exactly the same way a single draft does today.

CHANGE INSTRUCTIONS:

In prompts.py, add a new rule directly alongside the existing MULTIPLE QUALIFYING CLIENTS rule, not replacing it. The existing rule continues to apply as the default: when multiple clients qualify and the firm owner has not indicated they want all of them, still ask via OPTIONS, still never draft a placeholder. Add a new rule for the explicit case: if the firm owner clearly asks for drafts for all of the qualifying clients, using language like all of them, all three, everyone, each of them, or similar clear intent to cover every qualifying client rather than pick one, the model should produce multiple consecutive draft blocks in the same response, one per qualifying client, each using the exact same ---DRAFT:TYPE--- through ---END DRAFT--- format already established, each with its own accurate CLIENT line naming that specific client, and each with content genuinely personalized to that client's real situation, not a copy-pasted generic template repeated with only the name swapped. Never produce a placeholder in any of the batch drafts, the same absolute rule from the existing single-draft instructions applies to every draft in a batch.

In ConciergePanel.tsx, change parseDraftFromResponse so that instead of finding only the first occurrence of a draft block, it finds every occurrence in the message text, returning an array of parsed draft objects instead of a single object or null. Each element in the array should have the same shape currently returned for a single draft: type, content, source, clientName. The cleanedResponse, the display text with all draft blocks stripped out, should be computed once, based on everything before the first draft block begins, the same as it is today.

Change the Message type and every place that currently reads msg.draft as a single object to instead read msg.drafts as an array, which may be null, empty, or contain one or more entries. A single draft is simply an array of length one under this new shape, there is no need to maintain two separate code paths for the single-draft case and the batch case, one array-based rendering path handles both.

Update the rendering logic so that when msg.drafts contains more than one entry, each draft renders as its own separate, clearly delineated card, each with its own independent Copy button and its own independent Open to send button, and each tracks its own state independently, so sending or copying one draft does not affect the others, and the firm owner can review and act on each one in turn without needing to re-ask the question.

Update the Open to send handler so it operates on a single specific draft from the array, using that specific draft's own clientName for resolution exactly the way the existing single-draft logic already does, not the first or the last draft in the array by default.

Do not change how a single draft, the ordinary one-client case, looks or behaves to the firm owner, a batch of one should look and act exactly like today's existing single draft card.

Do not change the OPTIONS marker mechanism, the existing ask-which-client behavior, or anything about how a single, unambiguous draft gets triggered. This task only adds the explicit multi-draft path on top of what already exists.

VERIFY AFTER ACT:

grep -n "msg.drafts\|parseDraftFromResponse" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: consistent use of the new array-based field throughout, no remaining references to the old singular msg.draft anywhere in the file.

npm run build in frontend, expected zero TypeScript errors.

python3 -c "from app.main import app; print('OK')"

Also run the actual relevant test suite and paste the real output directly, not a summary, using the correct database and test file targeting, for example:

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jammpx_dev .venv/bin/pytest tests/test_phase7_billing.py -v 2>&1 | tail -60

Paste this real output as part of your own verification.

MANUAL VERIFICATION:

Full kill and restart of both servers, full .next wipe, this touches core message rendering state.

First confirm the existing single-client case still works exactly as before: ask a question where only one client qualifies, or where multiple qualify but you pick just one via OPTIONS, confirm one draft card appears and behaves exactly as it always has, Copy and Open to send both working correctly for that one client.

Then test the new batch case: ask a question where multiple clients qualify, such as which clients have overdue invoices, then explicitly ask for drafts for all three, or similar clear all-of-them language. Confirm multiple separate draft cards appear, one per real client, each with genuinely personalized content, no placeholders, no identical copy-pasted text across drafts. Confirm each draft's Open to send button navigates to that specific correct client, not the same one for all of them. Confirm copying or sending one draft does not affect or remove the others.

Report pass or fail individually for the single-client regression check and the new batch case.

GIT:
git add -A
git commit -m "add real multi-client batch drafting: when a firm owner explicitly asks for drafts for all qualifying clients, the model now produces multiple genuinely personalized draft blocks in one response, each independently reviewable and sendable, built on the existing per-draft client resolution mechanism rather than a new parallel system"
git pull --rebase origin main
git push origin main