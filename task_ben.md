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

TASK: Add an absolute rule against stating any number not directly returned by a tool call this turn

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "Never produce a draft that contains a placeholder" /home/corby/jamm-os/app/api/concierge/prompts.py
grep -n "never mention" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm both exist, these are the two closest existing absolute rules in tone and strength, use them as the model for how this new rule should read.

WHAT IS WRONG:

Confirmed live, with direct evidence from the new per-tool-call logging: a question about portal login activity resulted in only one tool call, get_portal_inactive_clients, which returns only an inactive count, a threshold, and a client list. The model's response stated additional specific numbers, such as a count of how many clients have portal access enabled and how many have ever logged in firm wide, that do not exist anywhere in that tool's return value and were not supplied by any second tool call, confirmed by the same log showing only one tool executed this turn. The model fabricated specific, confident sounding statistics with no real data behind them, delivered in the same sentence and with the same tone as the one real number that did come from the tool. This is a direct violation of the core standard that the agent never fabricates a specific number.

CHANGE INSTRUCTIONS:

Add a new absolute rule, in the same section and with the same strength as the existing rule against placeholder client names in drafts: the agent must never state any specific number, count, percentage, or statistic in a response unless that exact number was directly returned by a tool call made in that same turn. If the agent wants to say something is likely true or explain probable context, it must say so in qualitative terms only, without inventing a specific figure to make the explanation sound more precise or complete than the real data supports. Give a concrete negative example: if a tool returns an inactive client count of zero with no other data, the agent must not also state how many clients have portal access enabled or how many have ever logged in unless a tool call in that same turn actually returned those specific numbers. State plainly that a real number and an invented number delivered in the same confident tone are indistinguishable to the firm owner, which is exactly why this rule has no exceptions.

VERIFY AFTER ACT:

grep -n "never state any specific number\|directly returned by a tool call" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

MANUAL VERIFICATION:

Restart backend. Ask which clients haven't logged into their portal recently, with the backend terminal visible and filtered for Tool executed. Confirm only get_portal_inactive_clients fires, and confirm the response this time contains only the real number that tool actually returns, with no additional invented statistics about portal enablement or firm wide login counts.

GIT:
git add -A
git commit -m "add an absolute rule against stating any number not directly returned by a tool call in that same turn, closing a confirmed live fabrication where the model invented specific portal enablement statistics with no real data behind them, delivered with the same confidence as the one real number a tool actually returned"
git pull --rebase origin main
git push origin main