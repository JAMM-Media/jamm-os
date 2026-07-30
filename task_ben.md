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

TASK: Fix the count-to-message spacing on ContextualBanner so the count reads as part of the sentence instead of a disconnected element

USE: claude sonnet

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Confirm the outer flex container currently applies gap-3 equally between the count span, the message paragraph, and the button, causing the count and message to appear as visually disconnected as the message and button, even though the count and message are meant to read together as one sentence.

WHAT THIS IS:

Direct, live feedback tonight: with the earlier duplicate-count fix removing the leading number from the message text, the bold count badge now sits with a visibly oversized gap before the message text, making "4" and "overdue invoices totaling $4,750.00" look like two disconnected pieces rather than one flowing phrase. The person specifically said they like the bold count but not the spacing. The button correctly needs its own separation from the text, that part should not change.

CHANGE INSTRUCTIONS:

Wrap the count span and message paragraph together in a new inner div using flex items-baseline gap-1.5 and flex-1, so they sit close together as one phrase. Move flex-1 from the message paragraph onto this new wrapping div instead. Keep the outer container's existing gap-3 as the separation between this new wrapped group and the button, so the button's spacing is unaffected. Do not change any tone's colors, the button styling, or anything else in this file.

VERIFY AFTER ACT:

grep -n "items-baseline gap-1.5" /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Visit Billing with a real overdue invoice present. Confirm the count and message now sit close together reading naturally as one sentence, for example "4 overdue invoices totaling $4,750.00" with normal word-level spacing, while the Ask Concierge button still sits clearly separated on the right.

Visit /dev/concierge-kit, confirm the green and amber ContextualBanner examples show the same tightened spacing.

Report pass or fail for both checks.

GIT:

git add -A

git commit -m "fix ContextualBanner's count-to-message spacing so the bold count reads as part of the sentence instead of a disconnected element, wrapping the count and message together with tight baseline spacing while keeping the button's separate spacing from the text unchanged, per direct feedback tonight after the duplicate-count fix left an oversized gap between the count badge and the message text"

git pull --rebase origin main

git push origin main