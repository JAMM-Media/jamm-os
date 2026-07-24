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

TASK: Add a deterministic backend check for show briefing again requests, guaranteeing the required action marker always fires regardless of exact phrasing

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '460,500p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def morning_briefing_detail" -A 25 /home/corby/jamm-os/app/api/concierge/route.py
sed -n '1320,1340p' /home/corby/jamm-os/app/api/concierge/prompts.py
grep -n "show_briefing_again" -A 15 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Read the full __OPEN__ bypass block in route.py completely, and the full morning_briefing_detail endpoint completely, before writing anything. This task's whole point is removing model discretion from a structural requirement, matching the same pattern already proven correct for the __OPEN__ sentinel in this exact file.

WHAT THIS IS:

Confirmed live tonight: asking can I see the morning briefing again did not trigger the real show_briefing_again flow at all. The backend log showed Tool executed: get_daily_brief, an entirely different, ordinary tool call, with no show_briefing_again marker generated anywhere. The model answered as a normal conversational question and, having seen the required exact opening phrase Here's your briefing again in its own system prompt instructions, appears to have reused that phrase inappropriately without generating the required CONCIERGE_ACTION marker that the frontend depends on to actually fetch the real briefing detail and enable the download button. This is the exact same reliability failure mode already found and fixed twice tonight for the OPTIONS marker and for get_overdue_invoices, a natural language instruction, no matter how explicitly worded, cannot guarantee compliance for a case that must never fail. The fix pattern that already worked for those cases is a deterministic backend check that removes the model's discretion entirely, not a third rewording of the same prompt instruction.

CHANGE INSTRUCTIONS:

Add a deterministic intent check in concierge_chat, following the same structural pattern as the existing __OPEN__ sentinel bypass immediately above it in this file. Detect whether the user's most recent message is asking to see the morning briefing again, using a reasonably broad keyword match, such as containing briefing together with again, show, or see, in any order or combination, so real phrasing variety is covered, not just one exact string.

When this intent is detected and the firm has already received a briefing today, confirmed via current_firm.briefing_sent_at being set to today's date, bypass the main conversational model's own discretion for the structural parts of this response. Reuse the exact same underlying content generation already used by the morning_briefing_detail endpoint to produce the real, live briefing content, do not duplicate this logic in a second place. Construct the final response deterministically in code: the fixed line Here's your briefing again, then the real generated briefing content, then the required marker line, CONCIERGE_ACTION: {"type":"show_briefing_again"}, exactly matching the frontend's existing expected format, on its own final line, every single time, regardless of the model's own judgment.

If the firm has not received a briefing yet today, or briefing_sent_at is not set at all, do not trigger this bypass, let the conversation proceed normally, since there is no prior briefing to show again in that case.

Log a clear, distinct line, similar in spirit to the existing Tool executed logging, whenever this deterministic bypass fires, so this exact flow can be directly confirmed working from the backend log going forward, the same way tool execution already can be.

VERIFY AFTER ACT:

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible.

Ensure a briefing has already been shown today for the test firm, resetting and retriggering it first if needed. Ask can I see the morning briefing again, exactly the phrasing that failed live tonight, confirm the backend log now shows the new deterministic bypass log line firing, confirm the response correctly begins with Here's your briefing again, confirm real briefing content follows, and confirm the required CONCIERGE_ACTION marker line is present, not just implied.

Ask at least two different rephrasings, such as show me my briefing again and can I see today's briefing once more, confirm the same deterministic behavior holds for each, not just the one exact phrase that was originally tested.

Confirm the download briefing button actually becomes available and functional after this flow, since that is the real, functional consequence of the marker being present or absent, not just a cosmetic detail.

Separately, confirm a normal question unrelated to the briefing, such as which clients have overdue invoices right now, is completely unaffected and does not accidentally trigger this new bypass.

Report pass or fail individually for all three rephrasings, the download button functionality, and the unrelated-question regression check.

GIT:
git add -A
git commit -m "add deterministic backend bypass for show briefing again requests, matching the same pattern already proven correct for the __OPEN__ sentinel, since confirmed live tonight the model failed to generate the required CONCIERGE_ACTION marker for a real, natural phrasing of this request, silently disabling the briefing download feature, the third confirmed instance tonight of a natural language instruction alone failing to guarantee compliance for a case that must never fail"
git pull --rebase origin main
git push origin main