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

TASK: Revert tool-use loop from the temporary claude-sonnet-5 pin back to claude-fable-5, now that access has been restored and extended

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '835,855p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm this matches exactly: a comment block explaining the temporary substitution starting at line 838, followed by model="claude-sonnet-5" at line 849. Confirm this is the only occurrence of claude-sonnet-5 or claude-fable-5 anywhere in this file before editing.

WHAT THIS IS:

The tool-use loop was temporarily pinned to claude-sonnet-5 while claude-fable-5 was suspended under an export control directive. That suspension was lifted and access has since been restored and extended, but this code was never reverted back. Every tool-use response tonight, including every test performed while diagnosing and fixing the OPTIONS marker reliability issues, has actually been running on claude-sonnet-5, not claude-fable-5.

CHANGE INSTRUCTIONS:

Remove the entire TEMP comment block explaining the substitution, lines 838 through 847 as confirmed above. Change the model parameter from claude-sonnet-5 back to claude-fable-5. Do not add a new comment explaining this reversion, the git commit message will document why this changed.

Do not change any other model reference in this file, including the guard classifier on Haiku, the plain conversational path on Sonnet 4-6, or any of the Haiku calls for the briefing, detail, and polish endpoints. Only this one specific tool-use loop reference changes.

VERIFY AFTER ACT:

grep -n "claude-sonnet-5\|claude-fable-5" /home/corby/jamm-os/app/api/concierge/route.py

Expected: claude-fable-5 present, claude-sonnet-5 no longer present anywhere in the file.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible. Ask which clients have overdue invoices right now, confirm the response still works correctly end to end, tool_choice forcing still fires, the OPTIONS safety net still works, clickable buttons still render, exactly as they did on claude-sonnet-5. Time this response using the backend log timestamps, from the first httpx request to the final safety net check, and report the actual elapsed time, so we have a real point of comparison against tonight's earlier claude-sonnet-5 timings of roughly 1.6 to 4.5 seconds depending on question complexity.

Ask a second, different operational question to confirm general tool-use behavior is unaffected by the model change.

Report the exact timing found for the overdue invoices question and confirm the second question also worked correctly.

GIT:
git add -A
git commit -m "revert tool-use loop from the temporary claude-sonnet-5 substitution back to claude-fable-5, now that Fable 5 access has been restored and extended for another week, the export control suspension that necessitated the temporary swap has been lifted"
git pull --rebase origin main
git push origin main