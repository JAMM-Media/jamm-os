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

# Task: Make Concierge loading skeleton mirror the morning briefing's real layout

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '918,936p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current skeleton block: a fixed sequence of 9 generic bars of varying width simulating flowing paragraph text, with no visual distinction between what will become headers, bullet lists, or the stat/download-link footer once the real morning briefing content loads.

## WHAT IS WRONG

The morning briefing's real rendered content (confirmed via live testing) has a distinct structure: bold section headers (e.g. RECENT ACTIVITY with a pin icon), indented bullet list items beneath each header, a stat summary line near the bottom (e.g. "27 clients - 4 active engagements"), and a download link with an icon. The current skeleton is a flat sequence of paragraph-style bars with no indentation, no bullet shapes, and no footer-row shape, so there is a visible structural "snap" when the real content replaces it, since nothing about the skeleton's shape anticipated the list/header layout that was coming.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Replace the existing skeleton content (the block of 9 divs between the avatar div and the closing tags, lines approximately 924-934) with a version that mirrors the real layout: a header-shaped bar, several indented bullet-shaped bars beneath it, a second header-shaped bar, more indented bullets, a short divider-shaped bar, a stat-line-shaped bar, and a short footer-link-shaped bar at the end:

                <div className="h-3 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="flex flex-col gap-1.5 ml-3 mt-0.5">
                  <div className="h-2 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-2 w-4/5 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </div>
                <div className="h-3 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mt-2" />
                <div className="flex flex-col gap-1.5 ml-3 mt-0.5">
                  <div className="h-2 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-2 w-3/4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-2 w-2/3 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </div>
                <div className="h-px w-full bg-[#D5D8DE] dark:bg-[#444444] mt-2" />
                <div className="h-2 w-36 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mt-2" />
                <div className="h-2 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mt-1" />

This gives the skeleton two header-shaped bars (mimicking section headers like RECENT ACTIVITY), indented bullet-shaped lines beneath each, a thin divider, a stat-line-shaped bar, and a short final bar mimicking the download-briefing footer link. Do not change the outer wrapper div, the avatar circle, or the briefingLoading condition that controls when this renders. Do not touch any other file.

## VERIFY AFTER ACT

sed -n '918,940p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the new structure is present and properly nested.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open the Concierge panel on the dashboard for a firm where the morning briefing has not yet loaded (or clear sessionStorage to force a fresh load).
3. Confirm the loading skeleton now shows a shape resembling headers with indented bullets beneath them, a divider, and a short stat/footer line, rather than a flat sequence of paragraph-style bars.
4. Confirm the transition from skeleton to real content feels less jarring than before, with the real headers and bullets roughly landing where the skeleton's header and bullet shapes were.

Report what you observe at step 3.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "polish: Concierge loading skeleton now mirrors the morning briefing's real header/bullet/stat-line layout instead of generic flowing-paragraph bars, reducing the visual snap when real content loads"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.