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

TASK: Make inline bolded option names clickable, not just the buttons below

USE: Fable 5

VERIFY BEFORE ACT:
grep -n "parsedOptions\|msg.options" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "ReactMarkdown\|react-markdown" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm matches exist and confirm how message content actually gets rendered as markdown before writing any code.

WHAT THIS IS:

Options currently render correctly as clickable buttons below the message. The same option names also appear bolded inline within the message text itself. The standard now documented in JAMM_PX_Perfect_Assistant_Build.md under Section 1a is that the inline name itself should be just as actionable as the button, not a plain visual duplicate.

CHANGE INSTRUCTIONS:

When rendering message content where msg.options is present and non-empty, detect bolded text spans within the rendered markdown whose text exactly matches one of the strings in msg.options, and make those specific spans clickable, triggering the exact same send behavior as the corresponding button below. Bolded text not matching any option string exactly stays plain, unchanged.

Do not make every bolded span in every message clickable, only ones exactly matching a real option from msg.options on that specific message. Both the inline clickable name and the button row below should coexist and both work.

Visually, the clickable inline name should read as interactive without looking like a broken sentence, for example an underline on hover or a subtle color shift, not a full button style change.

VERIFY AFTER ACT:

npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full restart of both servers, full .next wipe. Ask the overdue invoices draft question again. Confirm both the button row and the bolded client names within the bulleted list are independently clickable and both correctly send the exact option text.

GIT:
git add -A
git commit -m "make inline bolded option names clickable in addition to the existing button row"
git pull --rebase origin main
git push origin main