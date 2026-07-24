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

TASK: Discourage formulaic report-style openers on plain factual answers

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '12,45p' /home/corby/jamm-os/app/api/concierge/prompts.py
sed -n '1325,1335p' /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the RESPONSE FORMAT section including the closing-line rule added earlier tonight, and confirm the exact, separate, deliberate hardcoded opening line required for the show briefing again flow, since this task must not touch or weaken that specific requirement.

WHAT THIS IS:

The same live audit that flagged the missing closing line on short factual answers also specifically flagged formulaic report-header style openers, such as here's a quick snapshot based on your firm's current data, as reading like a generated report rather than a person answering a question. No rule currently exists anywhere in the prompt governing this, the model produces these openers on its own with nothing discouraging it. This is the same root cause and same fix pattern as the closing-line rule added earlier tonight, applied to the other end of the response instead.

CHANGE INSTRUCTIONS:

Add a new rule to the RESPONSE FORMAT section, placed near the existing closing-line rule added earlier tonight: plain factual answers should not open with a generic report-style preamble such as here's a quick snapshot based on your firm's current data or similar framing that describes the act of answering rather than simply answering. The response should generally begin directly with the actual answer or the most relevant fact, the way a knowledgeable colleague would respond if asked the same question directly, not with a line announcing that an answer is about to follow.

Explicitly state this rule does not apply to the one required exact opening line for the show briefing again flow, here's your briefing again, which remains a fixed, deliberate format for that specific action and must not be affected by this new rule in any way.

VERIFY AFTER ACT:

grep -n "report-style preamble\|does not apply to.*briefing again" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: both present, confirming the new rule and its explicit exclusion are both there.

MANUAL VERIFICATION:

Restart backend. Ask which clients have overdue invoices right now, confirm the response now begins directly with the answer, not a generic preamble. Ask how are things looking or a similarly broad question likely to previously trigger a snapshot-style opener, confirm the same. Separately, trigger the show briefing again flow specifically and confirm its required exact opening line is completely unaffected by this change.

Report pass or fail for all three.

GIT:
git add -A
git commit -m "discourage formulaic report-style openers on plain factual answers, extending the same fix pattern already applied to closing lines earlier tonight to the other end of the response, per the same live audit finding, with an explicit exclusion preserving the one required exact opening line for the show briefing again flow"
git pull --rebase origin main
git push origin main