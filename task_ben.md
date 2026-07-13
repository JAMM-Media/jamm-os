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

TASK: Fix dark mode text contrast and wrong topic chip destination for time tracking questions

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "text-\[#374151\] dark:text-\[#9CA3AF\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "time_tracking: \['Go to Billing'\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm both exist before proceeding. Read the surrounding markdown rendering block and the full TOPIC_CHIPS object in full before editing.

WHAT IS WRONG, PART ONE:

The message bubble background dark mode fix applied earlier tonight correctly gave the bubble itself a proper dark background, but the base paragraph text color for concierge responses was never updated to match. It still uses dark:text-[#9CA3AF], a muted mid gray, while bold text and headers elsewhere in the same file already correctly use the much brighter dark:text-[#EDEEF0]. Confirmed live: regular response text remains hard to read against the new dark bubble background, while bold numbers are readable. The firm owner explicitly asked for regular text to match the same bright, readable color already used elsewhere, accepting that bold will differentiate by weight alone rather than by a separate color in dark mode.

CHANGE INSTRUCTIONS, PART ONE:

Change the base text color class for concierge role messages from dark:text-[#9CA3AF] to dark:text-[#EDEEF0], matching the same bright color already used for bold text, headers, and other high visibility elements throughout this file. Do not change the light mode color. Do not change this for the user role messages, which use a fixed white on navy that already works correctly in both modes.

WHAT IS WRONG, PART TWO:

The topic classifier already correctly identifies time tracking questions as the time_tracking topic, this is not a classification bug. The TOPIC_CHIPS map simply assigns time_tracking the same chip as billing, Go to Billing, instead of a distinct, correct destination. A dedicated /timesheets route already exists in the app with its own page, confirmed present in the frontend route tree. Sending a firm owner asking about logged hours to the billing page instead of the actual timesheets page is a real, avoidable mismatch.

CHANGE INSTRUCTIONS, PART TWO:

Change the time_tracking entry in the TOPIC_CHIPS object from ['Go to Billing'] to a chip pointing at the real /timesheets route, using whatever chip label and navigation pattern is already used for other entries in this same object, such as ['Go to Timesheets']. Confirm how chip labels actually trigger navigation elsewhere in this file, since the chip label alone may need to map to a real route path in whatever routing logic consumes these chip clicks, not just be a display string.

Do not change any other entry in TOPIC_CHIPS. Do not change the classifier itself, which is already working correctly for this specific case.

VERIFY AFTER ACT:

grep -n "dark:text-\[#EDEEF0\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "time_tracking:" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: the base message text class now included in the first grep's matches, and the second grep showing a timesheets destination rather than billing.

npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full restart, full .next wipe. In dark mode, ask a question with a longer response and confirm the regular sentence text is now clearly bright and readable, not just the bold numbers. Ask how many hours has each staff member logged this week, confirm the chip that appears now says something related to timesheets, not billing, and confirm clicking it actually navigates to the real /timesheets page.

GIT:
git add -A
git commit -m "fix dark mode base text color to match the already-correct bold text color, and fix the time_tracking topic chip pointing at billing instead of the real timesheets page"
git pull --rebase origin main
git push origin main