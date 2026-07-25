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

TASK: Write distinct per-firm-type opening greetings, and extend the OPTIONS clickable-names safety net to stalled engagements

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '325,368p' /home/corby/jamm-os/app/api/concierge/prompts.py
sed -n '460,485p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def get_stalled_engagements" -A 20 /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "_MULTI_CLIENT_TOOL_EXTRACTORS" -A 10 /home/corby/jamm-os/app/api/concierge/route.py

Confirm all four match exactly what is described below before editing.

WHAT THIS IS, PART ONE:

The very first message a firm ever sees from the Concierge, immediately after choosing whether they are tax prep, bookkeeping, or advisory, is word for word identical regardless of which one they picked, both in the model's own few shot examples in prompts.py and in the hardcoded fallback in route.py. The onboarding question is asked but nothing about the answer actually shapes what the firm owner sees next, and the text itself, let's get ready to work, I'm ready to help with anything you need, was flagged directly as robotic.

CHANGE INSTRUCTIONS, PART ONE:

In prompts.py, replace the three identical intake_example assistant responses, and the three identical if firm_type is X blocks, with three genuinely distinct greetings, one for tax_prep, one for bookkeeping, one for advisory, each nodding specifically to that kind of work, returns and deadlines for tax prep, the books and the close for bookkeeping, client work and planning for advisory, while keeping the exact same warm, plain register already established elsewhere tonight. Preserve the exact CONCIERGE_ACTION marker line and JSON shape following each greeting exactly as it currently is, only the greeting text itself changes.

In route.py, update the hardcoded open_text fallback in the same bypass block so it also branches on current_firm.firm_type, using the same three distinct greetings just written in prompts.py, word for word identical to what the model would say for that firm type, so the deterministic fallback and the model's own few shot behavior never diverge from each other.

WHAT THIS IS, PART TWO:

Confirmed live: asking how many stalled engagements do I have produced a real, correct, multi client answer with no clickable option buttons at all, unlike the equivalent overdue invoices question, which reliably produces clickable buttons every time. The root cause is confirmed: the OPTIONS marker safety net, _MULTI_CLIENT_TOOL_EXTRACTORS, built specifically because prompt only compliance for this exact behavior was already proven unreliable once tonight, only ever covered get_overdue_invoices and was never extended to any other multi client tool, including get_stalled_engagements, leaving it just as unreliable as the original problem this safety net was built to solve.

CHANGE INSTRUCTIONS, PART TWO:

Add a new entry to _MULTI_CLIENT_TOOL_EXTRACTORS for get_stalled_engagements, matching the exact existing style of the get_overdue_invoices entry, extracting the distinct set of real client names from that tool's actual returned data shape, confirmed by the verify step above, not assumed.

VERIFY AFTER ACT:

grep -n "_MULTI_CLIENT_TOOL_EXTRACTORS" -A 15 /home/corby/jamm-os/app/api/concierge/route.py

Expected: both get_overdue_invoices and get_stalled_engagements present.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart both servers. If possible, reset onboarding state for a fresh firm type selection, or otherwise confirm by direct reading that the three greetings in prompts.py and the three in route.py are now genuinely distinct from each other and match each other exactly per firm type.

Ask how many stalled engagements do I have, confirm clickable client name option buttons now appear, matching the same reliable behavior already confirmed for overdue invoices.

Report pass or fail for both, pasting the actual three greeting texts and the actual chat response for the stalled engagements question.

GIT:
git add -A
git commit -m "write three genuinely distinct opening greetings for tax prep, bookkeeping, and advisory firm types, replacing identical robotic text that made the onboarding question feel decorative rather than meaningful, keeping the deterministic route.py fallback and the model's own few shot examples in sync, and extend the OPTIONS marker safety net to get_stalled_engagements, since it was confirmed live to lack the same reliable clickable client names already working for get_overdue_invoices, the safety net having never been generalized past the one tool it was originally built for"
git pull --rebase origin main
git push origin main