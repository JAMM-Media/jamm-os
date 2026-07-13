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

TASK: Fix topic classifier double-counting overlapping keywords within the same bucket

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '232,320p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def _classify_topic" -A 15 /home/corby/jamm-os/app/api/concierge/route.py

Confirm current state matches what is described below before editing.

WHAT IS WRONG:

_classify_topic scores each topic bucket by summing one point per keyword found as a substring of the user's message, with no deduplication. Several buckets contain a shorter keyword and a longer keyword where the shorter one is a substring of the longer one, for example staff and staff member both exist in the staff bucket's keyword set, and team and team member both exist there too. Any message containing the longer phrase also necessarily contains the shorter one, so it gets counted twice for what is conceptually a single mention. Confirmed live: the message how many hours has each staff member logged this week scores time_tracking at 1 via hours, operational_data at 1 via week, but staff at 2, via both staff and staff member matching independently, causing staff to incorrectly win outright even though the message is fundamentally a time tracking question. This is not a keyword coverage gap, it is a scoring mechanism flaw that will recur anywhere else a keyword set contains one phrase that is a substring of another phrase in the same set.

CHANGE INSTRUCTIONS:

Change the scoring logic inside _classify_topic so that within a single topic's keyword set, a shorter keyword does not count as a separate point if a longer keyword that contains it as a substring has already matched. Concretely, for each topic, first find all keywords that actually match the message, then before scoring, remove any matched keyword that is itself a substring of a different matched keyword in the same set, so only the longest, most specific match for that particular mention contributes to the score. Do not change matching across different topics, only deduplicate nested matches within the same topic's own keyword set.

Do not add, remove, or reword any actual keyword in any topic bucket. This is purely a fix to how matches are counted, not a change to what counts as a match.

VERIFY AFTER ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _classify_topic
result = _classify_topic('How many hours has each staff member logged this week?')
print('classified as:', result)
assert result == 'time_tracking', f'expected time_tracking, got {result}'
print('PASS')
"

Expected: classified as: time_tracking, then PASS. Paste this exact output, not a paraphrase of it.

Also run the full existing test suite relevant to the concierge module, if one exists, and paste the real pytest output directly, not a summary:

pytest tests/ -k concierge -v 2>&1 | tail -40

Paste this real output as part of your own verification, do not simply state that tests pass without showing the actual run.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Ask how many hours has each staff member logged this week, confirm the chip is now Go to Timesheets, not Go to Settings. Separately ask a genuine staff related question with no time or hours language at all, such as which staff member has the lightest workload right now, confirm this still correctly produces the staff related chip, Go to Settings, so the fix did not overcorrect and break the legitimate staff classification case.

GIT:
git add -A
git commit -m "fix topic classifier double-counting overlapping keywords within the same bucket, such as staff and staff member both matching independently, which was causing questions like how many hours has each staff member logged to misclassify as staff instead of time_tracking due to an inflated score rather than an actual keyword gap"
git pull --rebase origin main
git push origin main