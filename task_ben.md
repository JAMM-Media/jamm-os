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

TASK: Fix the client detail page's portal-invite SuggestionCard to only appear when it's genuinely informative, not a redundant restatement of the always-visible Send Portal Link button

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '440,455p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

grep -n "createdAt" /home/corby/jamm-os/frontend/src/lib/api/clients.ts

Confirm the SuggestionCard currently renders whenever portalInviteSentAt is null, with no time threshold at all, meaning it appears immediately for a client created moments ago just as much as one created months ago, and confirm createdAt is already available on the client object in ISO string form. Confirm this before editing.

WHAT THIS IS:

Confirmed live and directly by the person using it tonight: this card, as originally built, provides no real information the page did not already show, since a Send Portal Link button already sits permanently visible just below it regardless of state. The feedback was specific and correct: the card should only appear when it is surfacing something the firm owner might genuinely not have noticed, not simply restating an always-available manual control. The real, meaningful signal here is time: a client who was added recently and has not yet been invited is completely normal and not worth flagging, but a client who has existed for a while with no portal invite ever sent is a real thing that could easily go unnoticed among everything else on a busy owner's plate. This is also a deliberate first real test of a broader pattern the person wants across the product: information the assistant surfaces directly in context because it is genuinely worth noticing, not a duplicate call to action for something already visible.

CHANGE INSTRUCTIONS:

Compute the number of days between the client's createdAt and the current date. Only render the SuggestionCard when portalInviteSentAt is null AND this computed age is 10 or more days. Update the card's message to state the real, specific fact driving the suggestion, for example stating the client's name and that it has been over a specified number of days since they were added with no portal invite sent yet, using real computed values, not a static string. Keep the existing onAction behavior exactly as it is, still only opening the panel and highlighting the existing Send Portal Link button, never sending anything automatically. Do not change the 10 day threshold to any other number without it being stated explicitly as a real, deliberate choice, and do not change how portalInviteSentAt itself is computed or fetched.

VERIFY AFTER ACT:

grep -n "10\|daysSince\|createdAt" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx | grep -i portal

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Find or create a client added within the last few days with no portal invite sent. Confirm the SuggestionCard does NOT appear for them, since this is normal and not yet worth flagging.

Confirm the card DOES still appear for Robert & Carol Tanner or another client old enough to cross the 10 day threshold with no invite ever sent, and confirm the message now states the real, specific number of days and the client's real name rather than generic text.

Report pass or fail for both checks individually, including the actual message text shown.

GIT:

git add -A

git commit -m "add a real 10 day age threshold to the client detail page's portal-invite SuggestionCard, fixing direct feedback tonight that the card as originally built provided no information beyond what the always-visible Send Portal Link button already showed, now only surfacing when a client has genuinely gone unnoticed for a meaningful length of time with no invite ever sent, with the card's message stating the real computed values rather than static text"

git pull --rebase origin main

git push origin main