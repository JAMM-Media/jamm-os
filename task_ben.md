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

TASK: Fix three real, confirmed Dashboard visual issues, safely scoped to Dashboard's own local code without touching shared design tokens

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '30,65p' /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx

sed -n '515,530p' /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx

grep -n "animate-pulse" /home/corby/jamm-os/frontend/src/components/billing/InvoiceCard.tsx

Confirm MetricCardSkeleton already exists and already uses animate-pulse, but with bg-surface-border dark:bg-dark-border, not matching the bg-[#D5D8DE] dark:bg-[#444444] convention already established in Billing and Engagements. Confirm the actual bare-text loading state, "Loading dashboard...", is a separate, earlier code path that renders when metrics is still null, with no skeleton UI of any kind, and confirm this is the real gap a live audit tonight caught during a rapid navigate-and-screenshot test. Confirm MetricCard's alert variant currently uses dark:bg-status-red-text/10 for the Overdue Engagements card in dark mode, a real, measurably weaker treatment than its light mode equivalent, confirmed by the same audit.

WHAT THIS IS:

Three real, separately confirmed Dashboard visual issues from tonight's audit. First, the Overdue Engagements stat card, the single most urgent metric on the page, has a visibly weaker highlighted treatment in dark mode than in light mode, undermining its intended urgency. Second, the true first-paint loading state shows only plain centered text with no skeleton at all, inconsistent with the real skeleton loading pattern already used on Billing and Engagements. Third, the skeleton that does exist for the stat cards uses a different pulse-bar color than the established convention used elsewhere. All three fixes here are deliberately scoped to Dashboard's own local code and component-level styling only, not to the shared surface-card or dark-card design tokens used throughout the rest of the app, to avoid a wide, hard-to-verify blast radius this late.

CHANGE INSTRUCTIONS:

In MetricCard, strengthen the alert variant's dark mode treatment from dark:bg-status-red-text/10 to a visibly stronger opacity, for example dark:bg-status-red-text/20, enough to be clearly distinct from the neutral cards without needing to touch any shared token. Separately, strengthen MetricCard's own default, non-alert variant with a slightly more pronounced shadow or a subtle ring, applied only within this component, to improve its visual separation from the page background in both light and dark mode, without changing the surface-card or dark-card background tokens themselves.

In MetricCardSkeleton, change the pulse bar color from bg-surface-border dark:bg-dark-border to bg-[#D5D8DE] dark:bg-[#444444], matching the exact convention already used in Billing and Engagements skeletons.

Replace the bare "Loading dashboard..." text state with a real skeleton layout, reusing MetricCardSkeleton for the four stat card positions exactly as it is already used elsewhere on this page during a narrower loading window, plus simple placeholder skeleton blocks, using the same bg-[#D5D8DE] dark:bg-[#444444] animate-pulse convention, roughly approximating the shape of the page's other major sections below the stat cards, so the true first-paint loading experience is visually consistent with the rest of the app rather than a plain sentence.

VERIFY AFTER ACT:

grep -n "dark:bg-status-red-text/20\|bg-\[#D5D8DE\] dark:bg-\[#444444\]" /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx

grep -n "Loading dashboard" /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx

Expected: the alert opacity change and skeleton color convention both present, and the bare loading text either fully removed or only present as a genuine final fallback behind a real skeleton.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Visit the Dashboard in dark mode with at least one real overdue engagement present, confirm the Overdue Engagements card now shows a clearly, visibly distinct red-tinted treatment, not a barely-there tint.

Force a fresh load of the Dashboard, for example a hard refresh, and try to catch the very first paint, confirming a real skeleton layout appears briefly instead of plain loading text, as close as reasonably catchable given how fast the load may be.

Confirm the stat cards, once loaded, show a visibly stronger separation from the page background in both light and dark mode compared to before, without looking like a different visual style from the rest of the app.

Report pass or fail for each of these three checks individually.

GIT:

git add -A

git commit -m "fix three real Dashboard visual issues confirmed by tonight's audit: strengthen the Overdue Engagements card's dark mode alert treatment from a barely visible 10 percent tint to a clearly distinct 20 percent tint, replace the bare loading dashboard text state with a real skeleton layout matching the pattern already used on Billing and Engagements, and align the stat card skeleton's pulse bar color to the same established convention, all changes deliberately scoped to Dashboard's own local component styling rather than the shared surface-card or dark-card design tokens used throughout the rest of the app"

git pull --rebase origin main

git push origin main