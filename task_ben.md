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

TASK: Build a Dashboard home screen widget surfacing the most actionable Concierge notification, no panel required

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '980,1075p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
sed -n '1437,1470p' /home/corby/jamm-os/app/api/concierge/route.py
grep -n "class ConciergeNotification" -A 15 /home/corby/jamm-os/app/models/concierge_notification.py

Read the full existing notification rendering block in ConciergePanel.tsx completely, including the Copy and Open to send button logic and the client routing behavior, before writing anything new. This task must reuse this exact logic, not reimplement a second, divergent version of it.

WHAT THIS IS:

External research on B2B AI feature adoption found that capabilities living in a separate panel a user has to remember to open see meaningfully lower long term engagement than the same capability surfaced directly in a primary workflow view. A live audit separately praised the existing alert tray specifically for surfacing a genuinely useful, ready to send draft and an internal reminder without being asked, calling this the strongest engagement pull observed in the whole product. This task surfaces that same real value directly on the Dashboard itself, visible the moment a firm owner lands there, without requiring the Concierge panel to be opened at all. This is deliberately scoped as a real but contained test of whether panel placement is actually limiting engagement, not a full redesign of how the Concierge is positioned in the product.

CHANGE INSTRUCTIONS:

Add a new widget section to the Dashboard page, positioned prominently, near the top of the page alongside or just below the existing stat cards. It should call the existing GET /concierge/notifications endpoint, already used by the panel's alert tray, do not create a second endpoint or duplicate this logic.

From the returned notifications, select the single most actionable one to feature: prioritize any notification whose metadata contains a real draft field over ones that do not, and among those, select the most recently created one. If no notification with a draft exists, fall back to featuring the single most recent notification of any kind, shown as a plain informational item without draft actions. If there are zero notifications at all, the widget should not render anything, not even an empty state, it should simply not appear on the page.

Render the featured item using the exact same visual pattern already established for notifications inside the panel, the message text, and if a draft exists, the same Draft label box with Copy and Open to send buttons, reusing the exact same click behavior already implemented in ConciergePanel.tsx for both actions, including the same confirmation dialog before navigating to a client's Messages tab with the draft prefilled. Do not write new logic for these two buttons, extract or directly reuse what already exists.

Apply the design language already established for the rest of the redesigned Dashboard, using the real tokens, the display serif for the client name if one is associated with the notification, and the concierge accent color for this widget's own visual identity, consistent with how the Concierge's identity was established elsewhere tonight.

Do not change anything in ConciergePanel.tsx itself, its own alert tray must continue working exactly as it does today, completely unaffected by this addition. Do not change the notifications endpoint or the ConciergeNotification model.

VERIFY AFTER ACT:

npm run build in frontend, expected zero TypeScript errors.

Confirm by direct code comparison that the Copy and Open to send button logic in the new widget is either directly reused from or byte for byte identical to the existing panel implementation, not a divergent reimplementation, paste this confirmation explicitly.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers. Do not use Playwright or any browser automation tool to self verify this, at all, for any reason, including taking screenshots. All manual and visual verification is done by the user directly in the browser, reported back in chat.

Confirm a real notification with a draft currently exists for the test firm, if not, trigger one through whatever means already exists tonight for generating one. Load the Dashboard without opening the Concierge panel at all, confirm the widget appears showing this real draft, with working Copy and Open to send buttons that behave identically to the existing panel version. Confirm the existing panel alert tray still works completely normally and independently. Confirm the widget does not appear at all if there are zero notifications, rather than showing an empty or broken state.

Report pass or fail individually for the widget rendering and content accuracy, the Copy button, the Open to send button and its confirmation dialog, and the existing panel remaining unaffected.

GIT:
git add -A
git commit -m "add a Dashboard home screen widget surfacing the single most actionable Concierge notification, including its real draft with working Copy and Open to send actions reused directly from the existing panel implementation, allowing the Concierge's most valuable proactive output to be seen and acted on without requiring the panel to be opened at all, as a contained, real test of whether panel placement itself is limiting engagement before considering any larger architectural change"
git pull --rebase origin main
git push origin main