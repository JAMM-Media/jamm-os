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

TASK: Build the reusable inline AI component kit as an isolated, standalone layer, not wired into any real page yet

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '1,40p' /home/corby/jamm-os/frontend/src/components/ui/card.tsx

sed -n '1,20p' /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts

sed -n '1452,1481p' /home/corby/jamm-os/app/api/concierge/route.py

sed -n '75,120p' /home/corby/jamm-os/frontend/src/components/dashboard/ConciergeSpotlight.tsx

Confirm the Card primitive in ui/card.tsx, the ConciergeAction event system in conciergeEvents.ts, the real shape of GET /concierge/notifications (id, trigger_type, message, created_at, metadata), and ConciergeSpotlight's existing click-to-open-panel pattern all match what is described below before building anything.

WHAT THIS IS:

This is the first step of a larger, deliberate redesign of how the Concierge is positioned in the product, informed by real research done tonight: features embedded in a separate panel a user has to remember to open see meaningfully lower long-term engagement than the same capability embedded directly in the primary workflow. The long-term goal is an "always embedded" Concierge, similar in spirit to how Apple Intelligence or Superhuman surface AI inline rather than behind a chat window that must be deliberately opened. This is explicitly NOT a 72 hour, pre-launch task. It is the deliberate first phase of a project that begins after launch. Tonight's task is scoped narrowly and safely: build a small set of reusable, presentational components in isolation, wire zero of them into any real page, and change no existing page's behavior. A real notifications data source already exists and already works, GET /concierge/notifications, currently consumed only by the side panel's alert tray. This task does not change that endpoint or what triggers a notification, it only builds new ways to eventually display that same real data elsewhere.

CHANGE INSTRUCTIONS:

Create a new directory, frontend/src/components/concierge-inline, for this component kit, kept fully separate from the existing ConciergePanel.tsx so nothing about the current, working panel is touched or put at risk.

Build five components:

1. SuggestionCard: takes a notification object matching the real shape from GET /concierge/notifications (id, trigger_type, message, created_at, metadata) plus an optional primary action label and an onAction callback, plus an onDismiss callback. Build on top of the existing Card primitive from ui/card.tsx rather than duplicating its styling. Visually deferential per tonight's research, a quiet card, not a loud banner, using the concierge gold accent token already established tonight, consistent with ConciergeSpotlight's existing visual treatment.

2. ContextualBanner: takes a message, a count, a primary action label, and an onAction callback, styled using the existing status-green or status-amber tokens depending on a passed tone prop, matching the visual pattern of Intuit-style "ready to post" banners, for the eventual high-confidence batch action case.

3. GhostTextField: a thin wrapper component around a standard text input or textarea that accepts a suggestedCompletion string prop and renders it as faint placeholder-style text ahead of the cursor, with no live AI wiring yet, purely the visual and interaction shell for a future select-to-act or ghost-completion feature.

4. PersistentEntryButton: a small, always-visible button component styled with the existing brand-btn token, accepting an onClick callback, intended eventually to be the persistent, repositionable gateway into the full Concierge panel, replacing the current less discoverable entry point, but not wired to replace anything yet in this task.

5. ContextLoadedChatPreview: a small header component intended to sit at the top of the existing ConciergePanel when it is opened via a hand-off from one of the inline components above, accepting an openedFromLabel string prop and rendering it as a small "opened from: [label]" line. Build this as a new, separate, optional component. Do not modify ConciergePanel.tsx itself in this task, only build this new piece in isolation so it can be integrated later without touching the panel's existing logic tonight.

Build a single new internal route, frontend/src/app/(app)/dev/concierge-kit/page.tsx, rendering all five components with realistic mock data including at least one real-shaped notification object, so they can be viewed and reviewed directly in the browser without needing to touch or risk any real page. This route is temporary scaffolding for review, not a permanent part of the product.

Do not change ConciergePanel.tsx, ConciergeSpotlight.tsx, the notifications endpoint, or any existing page. Do not wire emitConciergeAction or any real event into these new components yet, they should be fully self-contained and driven only by props for this task.

VERIFY AFTER ACT:

find /home/corby/jamm-os/frontend/src/components/concierge-inline -type f

Expected: five new component files.

npx tsc --noEmit

git diff --stat

Expected: only new files under concierge-inline/ and the new dev route, zero existing files modified.

MANUAL VERIFICATION:

Restart the frontend.

Visit /dev/concierge-kit directly in the browser. Confirm all five components render with the mock data, in both light and dark mode, using real tokens, not placeholder colors.

Confirm no existing page's behavior changed, spot check the Dashboard and a client detail page load exactly as they did before this task.

Do not use Playwright or any browser automation for this check, verify visually yourself.

Report pass or fail for each of the five components individually, plus confirmation that no existing page changed.

GIT:

git add -A

git commit -m "build the first phase of the inline Concierge redesign: five reusable, presentational components (SuggestionCard, ContextualBanner, GhostTextField, PersistentEntryButton, ContextLoadedChatPreview) built in full isolation under a new concierge-inline directory with a temporary dev review route, wiring nothing into any real page and changing no existing file, informed by tonight's research on panel versus inline AI assistant engagement, explicitly scoped as post-launch foundational work rather than a pre-launch change"

git pull --rebase origin main

git push origin main