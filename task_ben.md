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

TASK: Add a dismissible glow state to PersistentEntryButton using the concierge gold token, and wire it into AppShell as the always-visible, real entry point into the Concierge

USE: claude sonnet

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/PersistentEntryButton.tsx

grep -n "conciergeOpen\|handleConciergeClose\|ConciergePanel" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

grep -n "@keyframes\|animate-pulse\|animate-glow" /home/corby/jamm-os/frontend/tailwind.config.ts

Confirm PersistentEntryButton currently has no glow/highlight state at all, only onClick and an optional label, styled with a static bg-brand-btn class. Confirm AppShell.tsx owns conciergeOpen and currently has no visible always-on entry point into the panel besides whatever currently opens it. Confirm whether any pulse/glow animation utility already exists in the tailwind config before deciding whether to reuse one or add a new one.

WHAT THIS IS:

Following tonight's research and a direct product decision: instead of a full-page glowing border (rejected as too dominant, borrowing Apple's real-time-listening visual language for a meaning it does not have, and risking the same alert-fatigue problem the research flagged), the decision was to add a small, contained glow specifically to the persistent entry button built earlier in Phase 1 of the inline redesign, using the concierge gold token already established as this feature's reserved brand color everywhere else tonight, not the brand-btn blue used for the portal-link ring, to keep gold consistently meaning "the Concierge has something to say" across the whole product. This button has existed only in isolation inside the Phase 1 dev review route until now; this task is also the first time it is wired into a real, permanent location in the app.

CHANGE INSTRUCTIONS:

Extend PersistentEntryButtonProps with a new optional boolean prop, hasSuggestion, defaulting to false. When true, apply a visible but restrained glow effect using the concierge gold token, for example a soft box-shadow or ring in the concierge color with a gentle pulse animation, applied only to this button, not to any surrounding page content. Keep the glow subtle enough to notice in peripheral vision without being distracting, consistent with the deference principle from tonight's research. When hasSuggestion is false, the button should render exactly as it does today, no visual change.

In AppShell.tsx, render PersistentEntryButton as a new, fixed-position, always-visible element (for example fixed to a corner of the viewport, not blocking the main content), wired to call setConciergeOpen(true) on click, the same mechanism the open-panel action already uses. This becomes a second, always-visible way to open the panel, in addition to however it currently opens; do not remove or change the existing entry point. For this task, hasSuggestion can be wired to a simple, real placeholder condition, true whenever notifications.length is greater than zero if that state is reachable from AppShell, or false otherwise if it is not, stating clearly which case applies rather than guessing. A more complete, cross-page notification-awareness wiring is a separate, future task, not this one.

VERIFY AFTER ACT:

grep -n "hasSuggestion" /home/corby/jamm-os/frontend/src/components/concierge-inline/PersistentEntryButton.tsx

grep -n "PersistentEntryButton" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Confirm the persistent entry button now appears in a fixed, always-visible position on at least two different pages, for example Dashboard and a client detail page, confirming it is genuinely app-wide and not page-specific.

Confirm clicking it opens the Concierge panel correctly.

If hasSuggestion could be wired to a real condition, confirm the glow visibly appears when that condition is true and is absent when false. If it could not be wired to a real condition in AppShell, confirm the button at minimum renders correctly with no glow, and report clearly that the glow trigger itself still needs real wiring in a future task.

Report pass or fail for each check individually.

GIT:

git add -A

git commit -m "add a dismissible, concierge-gold glow state to PersistentEntryButton and wire it into AppShell as a new, always-visible, app-wide entry point into the Concierge panel, chosen over an earlier full-page glow concept per direct product feedback and tonight's deference-focused research, keeping gold consistently reserved for 'the Concierge has something to say' rather than reusing the blue already used for the portal-link ring"

git pull --rebase origin main

git push origin main