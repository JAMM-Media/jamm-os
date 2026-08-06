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

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

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

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Replace the full-width edit-mode strip with small buttons directly in each widget's existing top-right corner, matching what was there before the strip, but fix the one real collision by moving Work in Progress's dollar value out of that corner instead of adding structural space to every widget.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 5 -A 30 "WidgetEditOverlay" "src/app/(app)/dashboard/page.tsx"

grep -n -B 5 -A 20 "function WIPWidget" "src/app/(app)/dashboard/page.tsx"

Paste the real output of both. Confirm the current full-width strip implementation from the prior fix, and confirm the real current header structure of WIPWidget, specifically where the dollar value currently sits relative to the label.

WHAT THIS IS:

Ben looked at the full-width strip in the browser and it looks like two stacked header bars, not one polished widget. He's right that this was overbuilt: only one of the 9 widgets, Work in Progress, actually has real content in the same top-right corner where the edit buttons need to go. Every other widget's header only has a title on the left with nothing on the right, so the small corner buttons never actually collided with them, the strip was solving a problem that only existed for one widget. The better fix is to remove the strip entirely, put small buttons back in the corner the way they looked before that change, and fix the one real collision by changing Work in Progress's own layout so its dollar value isn't in that corner anymore, moving it below the label instead of beside it, which also brings it in line with how the other stat cards already lay out label-then-value.

CHANGE INSTRUCTIONS:

Remove the WidgetEditOverlay full-width strip entirely, the flex column restructuring, and the flex: 1 / minHeight: 0 changes made in the prior fix. Replace it with small remove and minimize buttons absolutely positioned in the top-right corner of each widget, similar in size and placement to how they looked in the screenshot before the strip was added, keep them visually light, small icon-only buttons with a subtle background so they read as controls, not as another header bar. Keep pointer-events none on the underlying widget content while editMode is true, that part of the prior fix was correct and should stay.

In WIPWidget, change the header row so the dollar value and hours no longer sit on the right side of the same row as the "Work in Progress" label. Move them to their own row below the label, left-aligned, matching the general pattern already used in MetricCard where a label sits above its value. This is a real layout change to this one component, not a hack, it should look intentional in both edit mode and normal view, not just avoid the overlay collision.

Do not add any special-casing to the overlay logic itself for WIPWidget or any other widget, the overlay positioning stays generic and identical for all 9 widget types, the WIP fix lives entirely inside WIPWidget's own layout.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "WidgetEditOverlay" "src/app/(app)/dashboard/page.tsx"

git diff --stat "src/app/(app)/dashboard/page.tsx"

Report the real diff stat and confirm no other widget's rendering logic was touched besides WIPWidget's header and the overlay component itself.

MANUAL VERIFICATION:

Restart the frontend dev server, reload /dashboard, confirm the normal (non-edit) view of Work in Progress now shows its dollar value below the label rather than beside it, and looks intentional, not broken. Enter Edit Dashboard, confirm every widget now shows small corner buttons directly on the widget, no separate strip, and confirm Work in Progress's value is fully visible with no overlap now that it's no longer in the same corner as the buttons. Report back with a screenshot.

GIT:

Do not commit until Ben confirms it actually looks right in the browser.