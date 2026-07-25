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

TASK: Style the alert dialog to match the design system, and make the Dashboard widget a real doorway into the panel with a minimize option

USE: Fable 5

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/frontend/src/lib/hooks/useConfirm.tsx
cat /home/corby/jamm-os/frontend/src/components/ui/Modal.tsx
cat /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts
sed -n '1,40p' /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx
cat /home/corby/jamm-os/frontend/src/components/dashboard/ConciergeSpotlight.tsx
grep -n "window.alert\|notificationsExpanded" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Read all of this completely before changing anything, including the full useConfirm hook, since the new alert hook must mirror its exact structural pattern, not invent a different one. This task touches the shared event system used across the panel, the widget, and the app shell. The reveal animation and every existing panel behavior verified earlier tonight must not regress.

WHAT THIS IS, PART ONE, THE ALERT DIALOG:

Confirmed live: clicking Open to send on a notification with no identifiable single client, such as a multi client internal reminder, correctly falls back to a raw, unstyled native browser alert dialog, a plain black box reading localhost:3000 says, clashing completely with the considered design work done everywhere else in this product tonight. This exact same window.alert call exists in four places total, three already inside ConciergePanel.tsx from before tonight, one newly duplicated into ConciergeSpotlight.tsx. All four need the same fix.

CHANGE INSTRUCTIONS, PART ONE:

Build a new useAlert hook, in the same file location pattern as the existing useConfirm hook, following its exact structural approach, returning an alert function and an AlertDialog element to render. Internally, this should use the existing Modal component from ui/Modal.tsx directly, do not build a new modal shell from scratch, passing the message as the modal body and a single OK button as the footer, no cancel option, since this is informational only. Replace all four window.alert calls, three in ConciergePanel.tsx and one in ConciergeSpotlight.tsx, with this new hook, preserving the exact existing message text in each of the four cases.

WHAT THIS IS, PART TWO, THE WIDGET AS A DOORWAY:

The Dashboard widget currently functions as a second, disconnected surface rather than a genuine entry point into the Concierge. Clicking anywhere on the widget, outside its own Copy and Open to send buttons specifically, should open the real Concierge panel and automatically expand its notification tray to reveal this same notification already in view, turning the widget into a real shortcut into the assistant rather than a competing, separate experience. Separately, the widget needs its own minimize control, so it does not permanently occupy Dashboard space once seen, while remaining easy to bring back.

CHANGE INSTRUCTIONS, PART TWO:

Add a new action type to the ConciergeAction type in conciergeEvents.ts, open-panel, with an optional expandNotifications boolean field, matching the existing style of that type definition exactly.

In AppShell.tsx, add a new listener using the existing onConciergeAction subscription pattern, listening for this open-panel action type, calling the existing setConciergeOpen(true) when received. AppShell currently has no such listener at all, this is new.

In ConciergePanel.tsx, add handling so that when this open-panel action arrives with expandNotifications true, the existing local notificationsExpanded state is set to true, so the alert tray auto-expands to reveal the relevant notification the moment the panel opens.

In ConciergeSpotlight.tsx, add an onClick handler to the outer container div that calls emitConciergeAction with type open-panel and expandNotifications true. Add stopPropagation to the Copy and Open to send buttons' own click handlers so clicking either of them does not also trigger the outer container's click-to-open behavior, these two actions must remain fully independent of the new doorway behavior. Add appropriate hover styling to the outer container signaling it is clickable, such as a subtle border or background shift on hover, consistent with the existing design language, not a heavy or jarring change.

Add a minimize control to the widget, a small button in its header row, toggling a local minimized state. When minimized, render a condensed single line version showing only the notification's core message text with no draft box, no buttons, and a way to expand back to the full view, persisting this minimized preference in sessionStorage using a key such as jamm_concierge_spotlight_minimized so it does not reset every time the Dashboard reloads within the same session, but does reset for a genuinely new session.

Do not change anything about how the widget selects which notification to feature, that logic is already correct and unrelated to this task.

VERIFY AFTER ACT:

npm run build in frontend, expected zero TypeScript errors.

grep -n "window.alert" across the frontend src directory, expected zero remaining matches anywhere.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers. Do not use Playwright or any browser automation tool to self verify this, at all, for any reason, including taking screenshots. All manual and visual verification is done by the user directly in the browser, reported back in chat.

Trigger the exact same no-client-identified case that produced the raw browser alert earlier, confirm it now shows a properly styled modal matching the rest of the product instead.

On the Dashboard, with the panel closed, click somewhere on the widget outside its buttons, confirm the real Concierge panel opens and its notification tray is already expanded showing this same notification, without needing to click the alert bell separately.

Confirm clicking Copy and clicking Open to send on the widget still work exactly as before and do not also trigger the panel to open as a side effect.

Click the new minimize control, confirm the widget collapses to a condensed single line, confirm it can be expanded back, and confirm the minimized state persists across a page reload within the same session.

Confirm the existing panel's own alert tray, its expand and collapse behavior, and every draft action inside the panel itself still work exactly as they did before this task, completely unaffected.

Report pass or fail individually for the styled alert dialog, the click-to-open-and-expand behavior, the button click isolation, the minimize and persistence behavior, and the existing panel regression check.

GIT:
git add -A
git commit -m "replace all four raw native browser alert dialogs with a new styled useAlert hook built on the existing Modal component, and turn the Dashboard Concierge widget into a real doorway into the panel, clicking it opens the panel with its notification tray already expanded to the same item, while Copy and Open to send remain fully independent actions, and add a minimize control so the widget does not permanently occupy Dashboard space, persisted for the session"
git pull --rebase origin main
git push origin main