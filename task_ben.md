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

TASK: Force get_overdue_invoices to actually be called via tool_choice, since prompt instructions alone cannot guarantee it

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '795,825p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "_OPERATIONAL_KEYWORDS\s*=" -A 20 /home/corby/jamm-os/app/api/concierge/route.py

Confirm the tool-use loop matches exactly what is described below before editing.

WHAT IS WRONG:

tool_choice has never been set anywhere in this file, confirmed by direct search. Every tool-use API call has always defaulted to auto, meaning the model has always had full discretion over whether to call any tool at all, on every turn, including the very first one. Confirmed live, repeatedly, across multiple separate diagnostic sessions tonight: a question that clearly and specifically requires get_overdue_invoices sometimes results in the model answering from memory or general reasoning instead of calling the tool at all, despite an explicit, emphatically worded prompt instruction added earlier tonight specifically to prevent this. A natural language instruction to an LLM, no matter how strongly worded or how many times reinforced, cannot guarantee one hundred percent compliance, since the model's behavior on any given turn remains probabilistic. The Anthropic API provides tool_choice specifically to remove this discretion at the code level when a tool call must not be skippable, and it has never been used anywhere in this codebase.

CHANGE INSTRUCTIONS:

Add a narrow, specific detection function, separate from the existing broad _OPERATIONAL_KEYWORDS set, that determines whether a message is unambiguously and specifically about overdue invoices rather than some other operational topic that happens to share a keyword like overdue or outstanding. Base this on genuinely specific phrase combinations such as the co-occurrence of a word like invoice or invoices together with overdue, owe, owes, or outstanding, or explicit phrases like who owes us money or which clients have overdue invoices. Do not rely on the single word overdue alone, since that word already appears broadly across the operational keyword set for engagements, tasks, and other unrelated domains, and forcing this specific tool on unrelated questions would be a new bug, not a fix.

In the tool-use loop, on the first iteration only, iteration index zero, if this new specific detection function returns true for the current user's message, pass tool_choice as a forced choice of the get_overdue_invoices tool specifically, using whatever parameter shape the installed Anthropic SDK version expects for forcing a single named tool, confirm the correct shape from the SDK's own type definitions or documentation comments already present elsewhere in this codebase if any exist, do not guess at the exact parameter structure. On every iteration after the first, and on the first iteration when this specific detection does not apply, continue passing tool_choice as auto exactly as the implicit current default behavior, so the model retains normal discretion for every other kind of question and for every turn after the initial forced call.

Do not change the broader _OPERATIONAL_KEYWORDS set or _is_operational_question, which correctly and separately decides whether to enter the tool-use loop at all. This task only affects whether tool_choice is forced once inside that loop for this one specific, narrow case.

VERIFY AFTER ACT:

grep -n "tool_choice" /home/corby/jamm-os/app/api/concierge/route.py

Expected: present, conditionally applied only on the first iteration and only for the narrow overdue invoices detection.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for OPTIONS SAFETY NET and tool execution confirmation. In a single fresh conversation, ask which clients have overdue invoices right now at least ten times in a row, spaced normally. For every single one of the ten, confirm in the backend log that get_overdue_invoices was actually called on that turn, with no exceptions this time, not nine out of ten, not eight out of ten, all ten. Confirm the clickable buttons render every single time as a direct result.

Separately, ask an unrelated operational question that does not involve overdue invoices at all, such as which staff member has the lightest workload right now, and confirm this new forced tool_choice logic does not incorrectly interfere with it, that question should proceed exactly as it always has, calling whatever tool is actually appropriate for it, not get_overdue_invoices.

Report pass or fail individually for all ten overdue invoice attempts, and for the separate unrelated question check.

GIT:
git add -A
git commit -m "force get_overdue_invoices to be called via the API's own tool_choice parameter instead of relying solely on a prompt instruction, since prompt-only compliance has now been proven unreliable across multiple separate real test sessions tonight despite repeated reinforcement, closing this gap at the code level where it can actually be guaranteed rather than merely requested"
git pull --rebase origin main
git push origin main