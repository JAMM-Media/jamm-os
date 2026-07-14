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

TASK: Fix OPTIONS marker being dropped after last task's new paragraph broke rule adjacency

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "MULTIPLE QUALIFYING CLIENTS" -A 30 /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the exact current ordering: the MULTIPLE QUALIFYING CLIENTS rule, followed by the new does-not-carry-forward paragraph added in the previous task, followed by EXPLICIT BATCH DRAFTING. Read this entire block in full before editing.

WHAT IS WRONG:

Confirmed live via raw console output: after the previous task's fix correctly stopped the model from reattaching a stale draft to a fresh generic question, the model's response ends with plain prose, let me know if you would like a reminder drafted for any of them, and the OPTIONS marker is completely absent. This is not a frontend rendering issue, confirmed by inspecting the raw text directly, the marker was never emitted. The most likely cause: the new paragraph added in the previous task was inserted directly between the MULTIPLE QUALIFYING CLIENTS rule and its own OPTIONS marker is required every single time, with no exceptions sentence, breaking the adjacency between the rule and its enforcement language. This is the same category of failure already fixed once before tonight, where OPTIONS compliance degrades whenever the requirement is not stated immediately alongside the specific scenario it applies to.

CHANGE INSTRUCTIONS:

Reposition the does-not-carry-forward paragraph so it no longer sits between the MULTIPLE QUALIFYING CLIENTS rule and its own OPTIONS requirement sentence. Move it to appear immediately before the MULTIPLE QUALIFYING CLIENTS heading instead, as context that applies going into that rule, rather than interrupting the rule and its own enforcement language.

Additionally, explicitly restate the OPTIONS requirement within the does-not-carry-forward paragraph itself, do not rely solely on proximity to the original rule. Add a direct sentence such as: this fresh evaluation still requires the OPTIONS marker exactly as the rule above states, with no exception for questions that follow an earlier draft. Redundant restatement is intentional here, since the marker requirement has already needed reinforcement once tonight and should not depend on the model correctly inferring that an adjacent rule still applies after new instructions have been inserted nearby.

Do not change the actual content or meaning of either the MULTIPLE QUALIFYING CLIENTS rule or the does-not-carry-forward paragraph, only their ordering and the addition of one explicit restatement sentence.

VERIFY AFTER ACT:

grep -n "MULTIPLE QUALIFYING CLIENTS" -A 35 /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the does-not-carry-forward paragraph now appears before the MULTIPLE QUALIFYING CLIENTS heading, and confirm it now contains an explicit restatement of the OPTIONS requirement.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend only.

Recreate the exact sequence that surfaced this bug: ask about overdue invoices, pick one specific client and get a draft, then ask a completely fresh, generic question with no client specified, such as which clients have overdue invoices right now again. With the browser console open and filtered to CONCIERGE RAW, confirm the raw output now includes the OPTIONS marker with the real client names, and confirm the clickable option buttons actually render below the message this time, not just that the marker is present in raw text.

Separately, confirm the markdown-free draft fix from the previous task still holds, and confirm the batch drafting feature still works, asking for drafts for all three again.

Report pass or fail individually for the OPTIONS marker presence in raw output, the clickable buttons actually rendering, the markdown check, and the batch drafting check, all four separately.

GIT:
git add -A
git commit -m "fix OPTIONS marker being silently dropped after the previous task's new paragraph broke adjacency with its own required-every-time enforcement sentence, by repositioning the paragraph and explicitly restating the marker requirement within it rather than relying on proximity alone"
git pull --rebase origin main
git push origin main