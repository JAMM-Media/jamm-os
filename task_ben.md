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

TASK: Stop auto-offering a draft after pure information questions, only offer when the firm owner's own message actually requested action

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "you may append a short draft artifact" -A 15 /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the current three-condition rule matches what is described below before editing.

WHAT IS WRONG:

The current rule attaches a draft offer whenever a live data call returns a named client and the model judges the natural next action to be a communication. Confirmed live and confirmed by direct product feedback: a purely informational question, which clients have overdue invoices right now, with no request for action anywhere in it, still ends every time with a follow up asking which client to draft a reminder for. This is the agent assuming what the firm owner probably wants next instead of answering only what was actually asked, the same category of overreach this build has been correcting all session.

CHANGE INSTRUCTIONS:

Replace the third condition, the natural next action is a communication, which is currently judged by the model's own inference from the data alone, with a condition based on the firm owner's actual message: only attach a draft offer when the firm owner's own question contains real action language, such as draft, send, remind, email, follow up, reach out, or similarly explicit intent to act, not merely because the data happens to involve named clients who owe money. A purely informational question, phrased only as which, what, how many, or similar, with no action language present, should receive only the direct answer, with no draft offer appended at all.

State this plainly as a rule change: the presence of specific named clients in a tool result is not by itself sufficient reason to offer a draft. The firm owner's own words must contain the actual request for action.

Do not change the two other existing conditions, calling a live data function and the result containing a named client, those remain necessary but are no longer sufficient on their own.

VERIFY AFTER ACT:

grep -n "firm owner's own message\|action language" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

MANUAL VERIFICATION:

Restart backend. Ask which clients have overdue invoices right now, confirm the response now ends with only the data, no draft offer and no follow up question attached. Separately, ask something like who owes us money and needs a reminder, confirm this one still correctly offers to draft, since it contains real action language. Report both results.

GIT:
git add -A
git commit -m "stop automatically offering a draft after pure information questions, only offer when the firm owner's own message contains real action language, since the previous rule judged intent from the data alone and was appending a draft offer to every overdue invoice question regardless of whether the firm owner actually asked for one"
git pull --rebase origin main
git push origin main