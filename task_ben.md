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

TASK: Build a backend safety net that deterministically constructs the OPTIONS marker when the model omits it after a multi-client tool result

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '820,865p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def get_overdue_invoices" -A 30 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the current tool-use loop structure matches what is described below, and confirm the exact real shape of get_overdue_invoices's returned dict, specifically the field name holding the list of individual overdue invoices and the field name holding each invoice's client name, before writing any extraction code. Do not assume field names, read them directly.

WHAT IS WRONG:

The MULTIPLE QUALIFYING CLIENTS rule, requiring the OPTIONS marker whenever a live data call returns more than one named client, has now failed three separate times tonight for the exact same underlying reason across different specific triggers: a marker ordering bug, a prompt paragraph adjacency bug, and now, confirmed live after both of those were fixed, a case where the model simply did not include the marker in its response despite everything else being correct, including asking the right clarifying question in prose. This is not a wording problem that can be solved with a fourth prompt rewrite. A soft, natural language instruction to an LLM cannot guarantee one hundred percent compliance no matter how it is phrased, since the model's response is still generated probabilistically each time. The backend already knows with total certainty when a multi-client tool call happened and exactly which real clients it returned, since it executed that call itself. Relying on the model to remember to also write that same information back out in a specific marker format is fragile in a way that code-level enforcement is not.

CHANGE INSTRUCTIONS:

Immediately after the tool-use loop exits, at the point where final_text and filtered_final are computed, add a deterministic check and correction step, before this text is yielded to the frontend.

Track, across the full tool-use loop, whether get_overdue_invoices was called during this turn and what it returned, specifically capturing the list of individual overdue invoices and each one's client name from the real tool result already sitting in memory from execution.

After filtered_final is computed, check two things: whether get_overdue_invoices was called this turn and returned more than one distinct client, and whether filtered_final already contains an OPTIONS marker. If a multi-client result exists and no OPTIONS marker is present in the final text, and the response does not already contain a completed draft block, construct the correct OPTIONS marker directly from the real client names captured from the tool result, and append it to filtered_final in the same format the model would have used, before this text is sent onward to the rest of the existing pipeline, including the TOPIC marker logic and the SSE yield.

Build this in a way that is clearly extensible to other live data functions later, for example a small mapping of tool name to a function that extracts a list of client names from that specific tool's result shape, with get_overdue_invoices as the first and only entry for now. Do not attempt to wire up every other live data function in this task, that is deliberately out of scope, this task solves the one proven, repeatedly failing case.

Do not change the existing prompt instructions in prompts.py, this is a backend safety net operating independently of and in addition to those instructions, not a replacement for them. Do not change anything about how the OPTIONS marker gets parsed or rendered on the frontend, that logic is already correct and only needs a reliably present marker to work with.

VERIFY AFTER ACT:

grep -n "OPTIONS.*safety net\|_extract_client_names\|multi_client_tool" /home/corby/jamm-os/app/api/concierge/route.py

Confirm the new deterministic construction logic is present near where final_text and filtered_final are computed.

python3 -c "from app.main import app; print('OK')"

Also write a small standalone script that directly calls the relevant part of this logic with a fake tool result containing more than one client and no existing OPTIONS marker in the text, confirming the correct marker gets appended, and run it, pasting the real output:

python3 -c "
# construct a minimal test of the new extraction and append logic here,
# using a fake multi-client get_overdue_invoices style result and a fake
# response string with no OPTIONS marker, confirming the function under
# test appends the correct marker with the real names from the fake data
"

MANUAL VERIFICATION:

Restart backend only.

Ask which clients have overdue invoices right now at least five separate times in a row, spaced normally, not rapid fire, in fresh separate conversations if possible to avoid any interaction with the stale-draft fix from earlier. Confirm the OPTIONS marker and the clickable client buttons appear every single one of the five times, not most of them.

Separately, ask a question involving get_overdue_invoices where only one client actually qualifies, if achievable with the current test data, or reason about this from the code directly, and confirm the safety net does not incorrectly attach an OPTIONS marker when there is only one client, since that would be a new, different bug.

Report pass or fail individually for all five repetitions, and for the single-client case.

GIT:
git add -A
git commit -m "add a deterministic backend safety net that constructs the OPTIONS marker directly from real tool result data when the model omits it after a multi-client overdue invoices call, since the prompt instruction alone has now failed to guarantee this three separate times tonight despite being correctly worded and correctly positioned, built as an extensible registry so other live data functions can be added to this same mechanism later"
git pull --rebase origin main
git push origin main