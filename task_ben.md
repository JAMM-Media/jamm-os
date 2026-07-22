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

TASK: Build automatic possible-fabrication detection into the ConciergeQuestionLog, closing the gap where confident fabrications produce no signal at all

USE: Fable 5

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/app/services/concierge_service.py
sed -n '795,825p' /home/corby/jamm-os/app/api/concierge/route.py
sed -n '1040,1065p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def _execute_tool" -A 5 /home/corby/jamm-os/app/api/concierge/route.py
cat /home/corby/jamm-os/app/models/concierge_question_log.py
ls /home/corby/jamm-os/migrations/versions/ | tail -5

Read all of this in full before writing any code. This task changes a logging pipeline used by every single real question asked of the Concierge, mistakes here have wide blast radius.

WHAT THIS IS:

Confirmed live, twice tonight: a fully confident, non-hedging fabrication, inventing a nonexistent staff member with specific fake numbers, and separately, inventing specific portal enablement statistics, both went completely undetected by the existing low_confidence flag, which only matches a fixed list of hedge phrases such as i'm not sure or i don't have access. Neither fabrication contained any hedge language at all, both were stated with full confidence, so this existing detection mechanism structurally cannot catch this exact failure mode, no matter how long the hedge phrase list gets.

Both real fabrications found tonight share a genuinely detectable, code level signature in one of two forms. First form, the more reliable one: the question was correctly classified as needing live data, the tool-use path was correctly entered, but no tool actually executed successfully this turn, and the response still contained a substantive, specific-sounding answer. Second form, less reliable but still worth surfacing: the question never entered the tool-use path at all, meaning the classifier missed it, and the response from the plain conversational path contains patterns suggestive of fabricated specific firm data, such as dollar amounts, percentages, or a proper name paired with a specific number.

CHANGE INSTRUCTIONS:

Add a new nullable boolean column, possible_fabrication, to the ConciergeQuestionLog model, defaulting to false, with its own index matching the existing pattern already used for the low_confidence column. Write a proper migration for this, matching the naming and structure of the most recent migrations already in this repo.

In the tool-use loop in route.py, add a simple tracking mechanism, a boolean or counter, set to indicate at least one tool executed successfully this turn, updated wherever the existing Tool executed log line already fires, reusing that exact point rather than adding a second separate check.

Update log_question_asked in concierge_service.py to accept two new pieces of information: whether this question was on the tool-use path or the plain path, and whether any tool actually executed this turn if it was on the tool-use path. Compute possible_fabrication as follows: if on the tool-use path and no tool executed and the response is non-trivial in length, mark true, this is the reliable detector. If on the plain path, mark true only if the response contains a dollar sign, a percent sign, or a pattern matching two consecutive capitalized words immediately followed by a number, since this is a heuristic approximation, not a certainty, and should be conservative rather than trigger constantly on legitimate general knowledge answers. Do not mark possible_fabrication true if low_confidence is already true, since that is a different, already-visible category, this new flag exists specifically to catch confident-sounding fabrications that show no hedging at all.

Update both call sites of log_question_asked in route.py to pass through whatever new information is needed for this computation.

Update the /concierge-log endpoint to also return possible_fabrication for each entry, and add a query parameter allowing filtering by it, matching the existing pattern already used for low_confidence_only.

Update the frontend /concierge-log review page to visibly show this new flag on each entry, distinct from the existing low confidence badge, for example a differently colored badge reading possible fabrication, and add its own filter toggle alongside the existing low confidence only toggle.

VERIFY AFTER ACT:

grep -n "possible_fabrication" /home/corby/jamm-os/app/models/concierge_question_log.py /home/corby/jamm-os/app/services/concierge_service.py /home/corby/jamm-os/app/api/concierge/route.py /home/corby/jamm-os/frontend/src/app/concierge-log/page.tsx

Expected: present in all four locations, or wherever the actual review page file is located if the path differs, confirm the real path first rather than assuming.

Also write and run a standalone test proving the detection logic directly, not just that the code compiles, using realistic fake inputs matching tonight's two real fabrications, and paste the real output:

python3 -c "
# construct the actual detection function's real inputs here, simulating
# the tool-use path with zero tools executed and a substantive response,
# and separately the plain path with a fabricated-looking name and number,
# confirming both are correctly flagged true, and confirming a normal,
# real, tool-backed response is correctly flagged false
"

python3 -c "from app.main import app; print('OK')"
npm run build in frontend, expected zero TypeScript errors.

Run the actual migration against the real dev database and confirm it applies cleanly:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jammpx_dev .venv/bin/alembic upgrade head

MANUAL VERIFICATION:

Restart both servers.

Ask which employee is being used the most again, now that the classifier fix already makes this correctly call a real tool, confirm possible_fabrication is correctly false for this now-fixed case.

If there is any way to temporarily and safely simulate the original bug for a real end to end test, such as asking a question using a phrasing deliberately excluded from any keyword list, do so and confirm possible_fabrication comes back true for that response, logged and visible on the /concierge-log page.

Ask a normal, already-working question such as which clients have overdue invoices right now, confirm possible_fabrication is correctly false.

Report pass or fail individually for all three checks, and confirm the review page visibly shows the new flag.

GIT:
git add -A
git commit -m "add automatic possible_fabrication detection to ConciergeQuestionLog, catching confident non-hedging fabrications that the existing low_confidence hedge-phrase detector structurally cannot catch, since both real fabrications found tonight, an invented staff member and invented portal statistics, contained zero hedge language and were stated with full confidence, closing the gap where this class of failure could previously only be found by a human happening to ask the exact right question"
git pull --rebase origin main
git push origin main