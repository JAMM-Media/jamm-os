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

TASK: Diagnose and fix a visible hairline white sliver at the top-left and top-right corners of the Modal component. Confirmed by Ben as universal across the entire app, not isolated to Load Template, it appears on Create Engagement and most other modals too, meaning this lives entirely in the shared Modal.tsx component and one real fix there resolves it everywhere at once.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat src/components/ui/Modal.tsx

Paste the full real file. I want to see every layer of the modal's rendering, the backdrop, any wrapping div, the actual card element, and every border-radius, box-shadow, outline, and ring class applied at each layer. A border-radius mismatch between two stacked elements, for example a square-cornered shadow, ring, or outline sitting behind or around a rounded background, so a sliver of the squared layer peeks out past the rounded one in front, is the leading theory, but this needs to be confirmed against the real code, not assumed, since it's now confirmed to affect every modal in the app and deserves a precise fix, not a guess.

WHAT THIS IS:

A zoomed screenshot shows a thin white/light line right at the modal's top-left and top-right corners, outside the rounded curve of the modal's own background. Confirmed universal across the app by Ben, appearing on Create Engagement, Reset to Default, Save as Firm Default, Save as Template, Load Template, and most other modals, meaning the cause is entirely inside the shared Modal.tsx component itself, not anything specific to tonight's work. Fixing the real cause here fixes it everywhere at once, which is exactly why this is worth diagnosing precisely rather than working around it in any one instance.

CHANGE INSTRUCTIONS:

Based on what the real Modal.tsx code shows, identify the specific mismatch, most likely two elements at the same corner position with different border-radius values, or a shadow/ring utility that doesn't inherit the same rounded corners as the element it's applied to. State plainly in the report exactly which two layers and which specific classes are responsible, quoting the real lines, before applying a fix. Apply the minimal correct fix, most likely aligning the border-radius value across whichever layers are mismatched, or moving a shadow/ring to the correct element so it clips to the same rounded corners rather than sitting behind it with square corners. Do not add a workaround like overflow-hidden as a first resort if the real cause is a genuine radius mismatch, fix the actual mismatch, only use overflow-hidden if that turns out to be the real, correct fix for what the code actually shows.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

git diff --stat src/components/ui/Modal.tsx

This should be a small, targeted diff in one shared file.

MANUAL VERIFICATION:

Restart the frontend dev server only. Reload the app, open at least three different modals in different parts of the app, for example Load Template on the dashboard, New Engagement, and any settings modal, zoom in on each modal's top corners the way Ben's screenshot did, confirm the white sliver is gone on all of them, not just one. Report back with a screenshot of at least one modal's corner zoomed in enough to actually see whether it's fixed.

GIT:

git add -A
git commit -m "fix a hairline visual artifact at the top corners of every modal in the app, caused by [fill in the real cause found in Modal.tsx], confirmed by Ben as universal across Create Engagement, Load Template, Reset to Default, Save as Firm Default, Save as Template, and most other modals, one shared-component fix resolves it everywhere rather than needing per-modal patches"
git pull --rebase origin main
git push origin main
git log --oneline -3

Paste the real output of git log --oneline -3 showing the new commit hash present next to origin/main. Do not report this as done based on the push command running, confirm the real log output showing origin/main at the new hash.