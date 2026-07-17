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

TASK: Extend bold rule to cover key terms in general knowledge answers, not just tool-derived figures

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "key figures" -B 2 -A 5 /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the current bold rule's exact wording before editing.

WHAT IS WRONG:

The existing bold rule only covers dollar amounts, counts, and dates that directly answer a question, which are always tool-derived figures. Confirmed live: a general tax knowledge question with no firm data involved, what is a 1120-S used for, produced a completely unbolded wall of text, technically correct per the current narrow rule, but a real readability gap. Educational and definitional answers with no numbers in them still benefit from bolding the specific terms being defined, so a firm owner can scan the response quickly.

CHANGE INSTRUCTIONS:

Add a new sentence directly alongside the existing bold rule, not replacing it: also bold the specific term, form number, or concept being directly defined or explained in a general knowledge answer, such as a tax form number or a piece of terminology central to the question, even when the response contains no dollar amounts or other figures. Keep this restrained, bold only the one or two central terms actually being explained, not every noun in the response.

VERIFY AFTER ACT:

grep -n "term.*being.*defined\|central to the question" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

MANUAL VERIFICATION:

Restart backend. Ask what is a 1120-S used for, confirm the form name and key terms like S corporation are now bolded. Ask an unrelated firm-data question, confirm the existing figure-bolding behavior is unchanged.

GIT:
git add -A
git commit -m "extend bold formatting rule to cover key terms in general knowledge answers with no tool-derived figures, since educational responses were rendering as unbolded walls of text under the previous narrower rule"
git pull --rebase origin main
git push origin main