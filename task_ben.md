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

TASK: Strip markdown syntax from draft content, and fix stale draft reattachment on fresh multi-client questions

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "CLIENT_EMAIL:" -A 10 /home/corby/jamm-os/app/api/concierge/prompts.py
grep -n "MULTIPLE QUALIFYING CLIENTS" -A 20 /home/corby/jamm-os/app/api/concierge/prompts.py
grep -n "EXPLICIT BATCH DRAFTING" -A 20 /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm all three exist before proceeding.

WHAT IS WRONG, PART ONE:

Confirmed live: draft content generated for a client email contained literal markdown bold syntax, asterisks around a dollar amount, visible as raw text inside the draft box rather than rendered formatting. Draft content is plain text destined for an actual email sent to a real client, it is never rendered through the chat's markdown display, so any markdown syntax inside it appears as literal asterisks in the real message if the firm owner copies or sends it without noticing. This is a real risk, not a cosmetic issue, a client could receive an email with visible asterisks in it.

CHANGE INSTRUCTIONS, PART ONE:

Add an explicit rule directly in the draft rules section, applying to every draft type, not just CLIENT_EMAIL: draft content must never contain markdown syntax of any kind, including bold asterisks, italics, bullet dashes, or headers. Draft content is plain text only. State this as an absolute rule with a concrete negative example, similar in strength to the existing rule against placeholder client names, since that rule has proven effective at being reliably followed once stated this directly.

WHAT IS WRONG, PART TWO:

Confirmed live: after the firm owner selected a specific client and received a draft for that client, they then asked a completely fresh, generic question, which clients have overdue invoices right now, with no client specified and no reference back to the previous selection. The model incorrectly treated the earlier client selection as still applicable and reattached the same old draft to the new response, in addition to correctly listing all three current overdue clients. The MULTIPLE QUALIFYING CLIENTS rule should have applied fresh to this new question exactly as it would on a first ask, requiring OPTIONS and no draft, since the new question did not specify a client and multiple clients still qualify.

CHANGE INSTRUCTIONS, PART TWO:

Add an explicit instruction directly alongside the MULTIPLE QUALIFYING CLIENTS rule: a previously selected client from an earlier turn in the conversation does not carry forward to a new, generic question that does not itself specify a client or clearly continue the same specific request. Each new question that could produce a draft must be evaluated fresh, based only on what that specific question actually asks and what it specifically names, not on what was selected earlier for a different request. Only treat a new message as referring to a previously selected client if it is clearly and directly a continuation of that same specific request, such as the firm owner immediately following up with something like also draft one for the other invoice right after receiving a draft, not a standalone, generically phrased question asked afterward.

VERIFY AFTER ACT:

grep -n "never contain markdown syntax\|does not carry forward" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: both new instructions present.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend only, no frontend changes in this task.

Ask for a draft involving a dollar amount, confirm the draft content contains no asterisks or other markdown syntax anywhere, plain text only.

Recreate the exact sequence that caused the stale draft bug: ask about overdue invoices, pick one specific client and get a draft, then ask a completely fresh, generic question with no client specified, such as which clients have overdue invoices right now again. Confirm this new response lists the clients and asks which one via OPTIONS again, with no draft attached, rather than silently reattaching the earlier client's draft.

Separately, confirm the batch drafting feature from the previous task still works correctly, ask for drafts for all three again, confirm multiple distinct drafts still appear correctly, to make sure this change did not regress that feature.

Report pass or fail individually for the markdown check, the stale draft check, and the batch regression check.

GIT:
git add -A
git commit -m "strip markdown syntax from draft content since it is plain text destined for a real email not the chat display, and fix the model incorrectly reattaching a previously selected client's draft to a fresh, generic multi-client question that did not specify a client"
git pull --rebase origin main
git push origin main