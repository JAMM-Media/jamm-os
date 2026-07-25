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

TASK: Give the Overdue Engagements stat card real visual distinction from its neutral peer cards when overdue count is positive

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '30,50p' /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx
sed -n '555,570p' /home/corby/jamm-os/frontend/src/app/\(app\)/dashboard/page.tsx

Confirm the shared MetricCard component and the Overdue Engagements call site exactly as described before editing.

WHAT THIS IS:

An independent live audit specifically flagged that the Overdue Engagements card currently carries the same visual weight as neutral cards like Unbilled WIP, with the audit's specific suggestion being a larger size or a colored card background, not just red value text, which is the only distinction that currently exists. This is the single most urgent, time sensitive metric on the Dashboard when its count is positive, and it should draw the eye before anything else, not compete for attention equally with unrelated neutral stats.

CHANGE INSTRUCTIONS:

Add a new optional prop to MetricCard, something like variant, accepting a value such as alert, defaulting to the existing neutral treatment when not passed. When variant is alert, the card's background and border should use the existing status-red tokens already established elsewhere in this codebase, at a subtlety appropriate for a background tint, not a solid, jarring red fill, still clearly a card, just visually distinct from its neutral siblings.

At the Overdue Engagements call site specifically, pass this new variant conditionally, only when the real overdue count is greater than zero, using the same visibleOverdue.length > 0 condition already used for the text color. When the count is zero, the card should render with the existing neutral treatment exactly as it does today, this distinction only applies when there is something genuinely urgent to flag.

Do not change the other three MetricCard call sites, Revenue This Month, Outstanding AR, Unbilled WIP, they keep the existing neutral treatment unconditionally.

VERIFY AFTER ACT:

npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

Confirm in light mode that with overdue engagements present, the Overdue Engagements card now visually stands out from its three neutral neighbors, not just through red text but through the card itself. Confirm the other three cards are completely unchanged. Confirm in dark mode the same distinction holds and remains fully readable, not overly bright or jarring against the dark background.

Report pass or fail for light mode, dark mode, and confirmation the other three cards are unaffected, with a screenshot of the full stat card row in both modes.

GIT:
git add -A
git commit -m "give the Overdue Engagements stat card a distinct alert-tinted background when the overdue count is positive, addressing a live audit finding that this, the single most time sensitive metric on the Dashboard, currently carries identical visual weight to neutral stats like Unbilled WIP, with only its value text previously distinguishing it"
git pull --rebase origin main
git push origin main