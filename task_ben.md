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

TASK: Redesign Dashboard onto the new token system and typography, fix layout cutoff if confirmed real, and unify empty-state tone

USE: Fable 5

VERIFY BEFORE ACT:
grep -c "bg-\[#\|text-\[#\|border-\[#" /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx
sed -n '1,100p' /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx
grep -n "No deadlines\|No unbilled\|No documents\|Your runway" /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx
grep -rn "mr-\[400px\]\|width.*400\|ConciergePanel" /home/corby/jamm-os/frontend/src/app/\(app\)/layout.tsx

Read the entire 610 line file in full before changing anything. This page pulls real, live data, stat cards, staff utilization bars, an overdue engagements table with real action buttons, an awaiting signature list. This task must not touch any data fetching, any state, any calculation, any conditional logic, only visual presentation and static empty-state copy text. If unsure whether something is presentational or logical, treat it as logical and leave it untouched.

WHAT THIS IS:

Phase 1 and phase 2 of the visual redesign replaced generic Inter typography with a distinctive serif and sans pairing, refined the color tokens toward a warmer palette, and gave the Concierge panel real visual identity, confirmed working with no regressions. This page, the actual homepage every firm owner sees first every single day, was never touched and still hardcodes 58 raw hex values, meaning it still looks exactly like the old design. Confirmed directly, side by side in the same screenshot, the Concierge panel and this page now visually read as two different products, which looks unfinished rather than intentional. Separately, this page's empty state copy is inconsistent in tone: the upcoming deadlines empty state, no deadlines in the next 14 days, your runway is clear, keep it that way, sounds like a person and matches the warm, buddy-like tone this product is aiming for, while the unbilled work and awaiting signature empty states are flat and generic by comparison, an inconsistency, not a case of every empty state needing invented personality from nothing.

CHANGE INSTRUCTIONS:

Replace hardcoded hex values throughout this file with the equivalent real design tokens already established, matching the same migration pattern already proven on ConciergePanel.tsx, brand, surface, dark, status colors, and font-sans and font-display where appropriate.

Apply the display serif specifically to the large key figures on the stat cards, the dollar amounts and counts such as revenue this month, outstanding AR, unbilled WIP, and overdue engagements count, so a firm owner's eye is drawn to the numbers that actually matter first, matching the same treatment already applied to key figures inside Concierge responses.

Give the stat cards and section panels genuine visual separation from the page background, real elevation or a more considered surface treatment, rather than the current flat, barely distinguishable card boundaries.

Rewrite the unbilled work and awaiting signature empty state copy to match the tone already established and working well in the upcoming deadlines empty state, warm, human, specific to what is actually true, not generic. Do not change the deadlines empty state copy itself, it already works, use it purely as the tone reference for the other two.

If the verify step confirms the Concierge panel's fixed width is not accounted for anywhere in this page's or the surrounding layout's width or margin calculations, add the appropriate spacing so real dashboard content is never cut off or hidden behind the panel when it is open. If the verify step shows this is already handled correctly and the earlier screenshot was simply a narrow window, do not change anything here and state clearly in your summary that this was checked and found not to be a real issue.

Do not change the underlying data these components display, do not change the staff utilization bar calculations, do not change the overdue engagements table's action buttons or their behavior, only their visual styling.

VERIFY AFTER ACT:

grep -c "bg-\[#\|text-\[#\|border-\[#" /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx

Expected: significantly lower than 58, ideally at or near zero.

npm run build in frontend, expected zero TypeScript errors.

Confirm the stat card values, the staff utilization percentages, and the overdue engagements table rows are computed identically before and after by comparing the relevant calculation code directly, not just visually, paste this confirmation explicitly.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

Load the Dashboard in light mode, confirm it now visually matches the warm palette and typography already established in the Concierge panel, no longer reading as two different products side by side. Switch to dark mode, confirm the same and confirm full readability, this is the most important check given how much effort dark mode contrast took earlier tonight.

Confirm every real number on the page, revenue, outstanding AR, unbilled WIP, overdue engagement count, staff utilization percentages, and the overdue engagements table contents, are completely unchanged from before this task, only their visual presentation changed.

Confirm the three empty states, deadlines, unbilled work, and awaiting signature, now read with a consistent, warm tone.

If the Concierge panel cutoff was confirmed as a real issue and fixed, open the panel and confirm real dashboard content, including the overdue engagements count card, is now fully visible, not hidden behind the panel.

Report pass or fail individually for light mode, dark mode, data accuracy, empty state tone, and the panel cutoff fix if applicable.

GIT:
git add -A
git commit -m "redesign Dashboard onto the established token system and typography from phases 1 and 2, apply the display serif to key stat figures, give cards real visual separation, and unify empty state copy tone to match the already-working deadlines empty state, with zero changes to any underlying data, calculation, or interactive logic"
git pull --rebase origin main
git push origin main