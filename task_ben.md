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

# Task: Replace generic onboarding intro message with simple placeholder copy

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "Got it. Here are three things to work on first" /home/corby/jamm-os/app/api/concierge/route.py

Confirm the exact current message text and its location before editing. If this string is not found in route.py, search prompts.py instead:

grep -n "Got it. Here are three things to work on first" /home/corby/jamm-os/app/api/concierge/prompts.py

## WHAT IS WRONG

The current __OPEN__ response on first message after a firm has answered the onboarding firm_type question reads "Got it. Here are three things to work on first:" followed by three generic numbered suggestions. This framing line adds nothing the three suggestions don't already say, and the suggestions themselves are not personalized to the firm's actual data. This is intentionally being kept simple and honest for now, with real personalization (using get_firm_context data on bottlenecks and wins) deferred until that data pipeline is built out further, rather than faking personalization with generic phrasing now.

## ACTION

Locate the exact source of this message (wherever VERIFY BEFORE ACT found it) and replace the message text with:

Let's get ready to work. I'm ready to help with anything you need.

Remove the "Here are three things to work on first" framing and the three numbered suggestions entirely for this specific message. Do not change the firm_type onboarding question itself (the "what does your firm do most" message), only the message that follows it once firm_type is already known. Do not change any other message in this file.

## VERIFY AFTER ACT

grep -n "Let's get ready to work" /home/corby/jamm-os/app/api/concierge/route.py /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present in whichever file it was added to.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors (only relevant if any frontend string also needed updating; if this was backend-only, confirm no frontend changes were made).

## MANUAL VERIFICATION

1. Restart the backend.
2. Open a fresh Concierge session (clear sessionStorage or use a private window) for a firm with firm_type already set.
3. Confirm the first message reads "Let's get ready to work. I'm ready to help with anything you need." with no numbered list following it.
4. Regression check: confirm the firm_type onboarding question itself (for a firm with firm_type still null) is unchanged.

Report what you observe at step 3.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "copy: simplify Concierge opening message to honest placeholder text, removing generic non-personalized suggestions until real firm-data-driven personalization is built"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.