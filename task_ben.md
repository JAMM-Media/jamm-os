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

# Task: Fix word-reveal animation disappearing on responses that complete quickly

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '328,340p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm setRevealedWordCount(Number.MAX_SAFE_INTEGER) is called at line 333 inside the try block, before setStreaming(false) fires in the finally block.

grep -n "streaming && i === messages.length - 1" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the render condition that switches between the word-sliced reveal and full content rendering.

## WHAT IS WRONG

Confirmed via live testing: the word-reveal animation works on longer responses but disappears entirely on shorter ones, making the behavior inconsistent. Root cause: setRevealedWordCount(Number.MAX_SAFE_INTEGER) fires inside the try block synchronously before setStreaming(false) fires in the finally block. React batches both state updates together into a single render flush. The render condition streaming && i === messages.length - 1 becomes false the instant streaming goes false, so the word-sliced reveal path is never evaluated -- full content renders immediately, bypassing the reveal entirely. The snap-to-end was added to ensure any remaining unrevealed words appear after streaming ends, but this purpose is already served by the render condition switching to full-content display when streaming becomes false. The snap is therefore redundant in its intended effect but actively harmful to the reveal animation by racing with setStreaming(false).

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Remove the setRevealedWordCount(Number.MAX_SAFE_INTEGER) call entirely from the try block. Do not replace it with anything. The render condition already handles showing full content once streaming is false, so no snap-to-end mechanism is needed.

Also reset revealedWordCount back to 0 in the finally block alongside setStreaming(false), so the state is clean for the next message:

      } finally {
        setStreaming(false)
        setRevealedWordCount(0)
      }

This ensures the reveal counter does not carry over from one response to the next, which could cause the next response to start mid-reveal if the previous one ended with a high word count.

Do not change the reveal useEffect, the targetWordCountRef update effect, the render condition, or any other part of the streaming or reveal logic.

## VERIFY AFTER ACT

grep -n "MAX_SAFE_INTEGER" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: no matches -- the snap-to-end call is gone.

grep -n "setRevealedWordCount(0)" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present in the finally block.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask a short question that produces a 1-2 sentence response (e.g. "where are my clients?").
3. Confirm the response now reveals word by word even on short responses, not all at once.
4. Ask a longer question that produces a multi-line bulleted response.
5. Confirm the reveal is smooth and consistent on longer responses too.
6. Ask two questions back to back and confirm the reveal resets cleanly between them with no carry-over from the first response.

Report what you observe at steps 3 and 5.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: word-reveal animation now works consistently on all response lengths by removing the snap-to-end call that was racing with setStreaming(false) and preventing the reveal from running on short responses"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.