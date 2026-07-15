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

TASK: Fix OPTIONS safety net's corrected text never being transmitted to the frontend

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '888,940p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "\[FILTERED\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current structure matches exactly what is described below, and confirm how the frontend actually handles a [FILTERED] sentinel event, since the fix needs to reuse that exact same proven mechanism, not invent a new one.

WHAT IS WRONG:

The OPTIONS safety net's own internal logic is confirmed correct via backend logs: it correctly detects a multi-client tool result, correctly extracts real client names, and correctly appends a well-formed OPTIONS marker to filtered_final. However, the only existing mechanism that sends a corrected version of the response text to the frontend, the FILTERED sentinel and replacement text yield, only fires inside a conditional block that runs and completes before the safety net executes at all. The safety net's modification to filtered_final happens strictly afterward, with no yield statement following it anywhere. This means the safety net's correction is computed on the server and then never transmitted to the client under any circumstance, confirmed live: the backend log showed the marker being correctly constructed and appended, while the frontend received no marker at all and rendered no buttons.

CHANGE INSTRUCTIONS:

Restructure this section so there is exactly one final determination of the true, fully corrected response text, computed after both the leak filter and the OPTIONS safety net have had a chance to modify it, followed by exactly one yield of the FILTERED sentinel and replacement text pattern if and only if the fully corrected text differs from what was originally streamed to the client during generation.

Concretely: compute filtered_final from the leak filter as it does today, but do not yield the FILTERED sentinel immediately. Run the OPTIONS safety net logic against this filtered_final exactly as it already does, allowing it to further modify filtered_final if needed. Only after both of these steps have completed, compare this final version of filtered_final against the original final_text that was actually streamed to the client during generation, and if they differ at all, for any reason, whether from the leak filter, the safety net, or both, yield the FILTERED sentinel and the fully corrected filtered_final exactly once, containing every correction that was made.

Do not create two separate yield blocks for the two different correction sources. There should be one single source of truth for what the truly final, fully corrected text is, and one single transmission of it to the frontend when it differs from what was already streamed.

Do not change the frontend's handling of the FILTERED sentinel, it already works correctly, this fix only needs to make sure the safety net's correction is actually included in what gets sent through that existing, proven mechanism.

VERIFY AFTER ACT:

sed -n '888,945p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm there is now exactly one yield of the FILTERED sentinel pattern, positioned after both the leak filter and the safety net have both had a chance to run, not two separate yield blocks.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for OPTIONS SAFETY NET. In a single fresh conversation, ask which clients have overdue invoices right now at least eight times in a row, spaced normally, specifically trying to catch another case where the safety net actually has to construct and append a marker, not just cases where the model already included it correctly on its own. When the safety net logs that it appended a marker, confirm in the same moment that the browser actually shows the clickable buttons this time, not just that the backend log looks correct.

Report pass or fail individually for all eight attempts, and specifically flag which attempts, if any, involved the safety net actually firing versus the model including the marker on its own, since both cases need to work correctly now.

GIT:
git add -A
git commit -m "fix OPTIONS safety net correction never being transmitted to the frontend, since the only mechanism for sending corrected text ran before the safety net modified the response, meaning the safety net's own logic was already fully correct but its output was a dead end that never reached the client, confirmed via backend logs showing correct marker construction alongside no buttons rendering in the browser"
git pull --rebase origin main
git push origin main