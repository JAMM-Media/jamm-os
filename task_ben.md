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

TASK: Extract notification fetching into a shared, reusable hook so AppShell can know the real notification count without duplicating ConciergePanel's logic

USE: Fable 5

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/lib/hooks/useConciergeContext.ts

sed -n '100,115p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '270,300p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '540,558p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "notifications\|fetchNotifications\|dismissNotification" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm useConciergeContext.ts's exact pattern: a standalone hook, not a React Context provider, using a module-level Map as a shared cache with a TTL, called independently by any component that needs it. Confirm ConciergePanel.tsx currently owns notifications state, fetchNotifications, dismissNotification, and mark-as-read entirely locally, with fetching gated behind isOpen, plus a 60 second polling interval also gated behind isOpen. Confirm this exact current behavior before changing anything.

WHAT THIS IS:

The persistent entry button added earlier tonight has a hasSuggestion prop ready to use, but nothing currently wires it to anything real, because notification data only exists inside ConciergePanel.tsx's own local state, unreachable from AppShell.tsx where the button lives. This task follows the same pattern already established and working in this codebase for exactly this kind of cross-component data need, useConciergeContext.ts, rather than introducing a new, different pattern like React Context. This is real, live surgery on the single most heavily used and most tested file from this entire session, so the scope here is deliberately narrow: extract existing logic into a new hook, do not change what that logic does or how the panel behaves.

CHANGE INSTRUCTIONS:

Create a new hook, frontend/src/lib/hooks/useConciergeNotifications.ts, following the exact structural pattern of useConciergeContext.ts: a plain function-based hook, not a Context provider, with a module-level cache so multiple components calling this hook share fetched data rather than each independently polling the API. Move the notification fetching logic (the GET to /concierge/notifications, and the trigger-check POST currently combined with it) into this new hook. The hook should independently manage its own polling on a 60 second interval, not gated behind any panel-open state, since the entry point using it needs to know about notifications even when the panel has never been opened. Expose notifications, a loading or ready state, and a way to mark one as read or refetch, matching what ConciergePanel currently needs.

In ConciergePanel.tsx, replace its own local notifications state, fetchNotifications function, and the two isOpen-gated effects that call it, with a call to this new hook instead. Do not change any of the JSX that renders the alert tray, the dismiss button, the mark-as-read behavior, or the draft cards inside notifications, only change where the underlying data comes from. The panel's own trigger-check-on-open behavior can remain as an explicit refetch call into the new hook when the panel opens, if that preserves the existing immediate-refresh-on-open behavior, state clearly if this changes any existing timing.

In AppShell.tsx, call the new hook and pass hasSuggestion as notifications.length greater than zero into PersistentEntryButton, replacing the hardcoded false from earlier tonight.

Do not change PersistentEntryButton.tsx itself, its hasSuggestion prop already exists and works correctly. Do not change the dismiss-all or mark-as-read backend endpoints. Do not change trigger-check's own backend logic.

VERIFY AFTER ACT:

grep -n "useConciergeNotifications" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

grep -n "hasSuggestion" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

Expected: hasSuggestion no longer hardcoded to false, now driven by real notification count.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

With a real, unread notification present for the firm, confirm the persistent entry button in the corner now shows the gold glow even before the panel has ever been opened this session.

Open the panel, confirm the alert tray still shows the same notification, still dismissible, still mark-as-readable, exactly as it worked before this task.

Dismiss the notification from inside the panel, confirm the button's glow correctly turns off once the count reaches zero, without needing to close and reopen the panel.

Reload the page entirely, confirm notification state loads correctly fresh, both in the button and in the panel, with no console errors.

Report pass or fail for all four checks individually, since this task touches the most sensitive file from tonight's entire session and deserves the most careful verification of anything built so far.

GIT:

git add -A

git commit -m "extract ConciergePanel's notification fetching into a new, shared useConciergeNotifications hook, following the exact standalone-hook-with-module-level-cache pattern already established by useConciergeContext, so AppShell can now drive the persistent entry button's real gold glow from actual notification data instead of a hardcoded false, with ConciergePanel's own alert tray, dismiss, and mark-as-read behavior fully preserved and now sourced from the shared hook instead of local state"

git pull --rebase origin main

git push origin main