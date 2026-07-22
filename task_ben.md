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

TASK: Fix FILTERED replacement sentinel dropping all but the first line of corrected multi-line responses

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '788,800p' /home/corby/jamm-os/app/api/concierge/route.py
sed -n '1012,1025p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm both occurrences match exactly what is described below before editing.

WHAT IS WRONG:

Both places in this file that send a corrected replacement response after the FILTERED sentinel, one in the plain conversational path and one in the tool-use path, yield the entire corrected multi-line text as a single SSE data event: yield f"data: {filtered}\n\n" and yield f"data: {filtered_final}\n\n". When this corrected text contains internal line breaks, such as any bulleted list, the raw newline characters inside what is meant to be one field's value get misinterpreted by the browser's own line splitting on the frontend. Only the first line retains the required data: prefix, every line after the first internal newline loses it and gets silently dropped by assembleSSELines, which only keeps lines starting with data:. Confirmed live: a corrected response containing a bulleted list of four overdue invoices displayed only its first sentence, the entire bulleted list vanished, immediately after a separate, correct fix started properly consuming the FILTERED marker for the first time. That fix is not the bug, it simply exposed this pre-existing issue by finally causing the frontend to rely entirely on content that was already being sent maliformed.

CHANGE INSTRUCTIONS:

In both locations, replace the single yield of the entire corrected text with line by line yielding, splitting the corrected text on newlines and yielding each resulting line as its own separate data: prefixed SSE event, exactly matching the pattern already used safely elsewhere in this same file for the normal streaming loop, such as the existing while "\n" in buffer style splitting already present nearby. Do not change the FILTERED sentinel itself or anything before it, only how the corrected text that follows gets transmitted.

Apply this identically to both occurrences, the plain conversational path and the tool-use path, since both have the exact same bug.

VERIFY AFTER ACT:

sed -n '788,802p' /home/corby/jamm-os/app/api/concierge/route.py
sed -n '1012,1028p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm both now split the corrected text into individual lines before yielding, rather than yielding the whole multi-line string in one event.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers using restart_backend.sh and restart_frontend.sh, checking with lsof on both port 3000 and 3001 before wiping anything, given tonight's stale process issue.

Ask which clients have overdue invoices right now, the exact question already confirmed to trigger this failure. Confirm the full bulleted list of all four clients now displays completely, with no missing content and no raw FILTERED text visible anywhere.

Separately, ask several normal questions that should not trigger any filtering at all, confirm they still display exactly as they always have.

Report pass or fail for the multi-line filtered response and the normal-response regression check, individually.

GIT:
git add -A
git commit -m "fix FILTERED replacement sentinel yielding entire multi-line corrected responses as a single SSE event, which caused the browser's line splitting to drop every line after the first internal newline, silently truncating any corrected response containing a bulleted list or other multi-line content, exposed by the recent fix that made the frontend finally rely on this previously-malformed content"
git pull --rebase origin main
git push origin main