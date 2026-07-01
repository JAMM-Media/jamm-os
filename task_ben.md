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

# Task: Fix word-reveal not animating on short responses by firing the first tick immediately and reducing the interval

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '150,163p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current reveal useEffect: streaming guard, tick function incrementing revealedWordCount, and the initial setTimeout(tick, 35) that delays the very first tick by 35ms.

## WHAT IS WRONG

Confirmed via live testing: the word-reveal animation works on longer responses but not on short ones (1-2 sentences). Root cause: the tick chain starts with a 35ms delay before the first word is revealed. For short responses that complete streaming in under 35ms, setStreaming(false) fires in the finally block before the first tick ever runs. The useEffect cleanup cancels the pending timer, and the render condition streaming && i === messages.length - 1 is already false when React next renders, so full content appears with no reveal at all. The fix is to fire the first tick with no delay (using setTimeout(tick, 0) or calling tick() directly), and reduce subsequent ticks from 35ms to 15ms so more words reveal during the brief streaming window of even the shortest response.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Replace the reveal useEffect body:

  useEffect(() => {
    if (!streaming) return
    function tick() {
      setRevealedWordCount((prev) => {
        if (prev >= targetWordCountRef.current) return prev
        return prev + 1
      })
      revealTimerRef.current = setTimeout(tick, 35)
    }
    revealTimerRef.current = setTimeout(tick, 35)
    return () => {
      if (revealTimerRef.current) clearTimeout(revealTimerRef.current)
    }
  }, [streaming])

With:

  useEffect(() => {
    if (!streaming) return
    function tick() {
      setRevealedWordCount((prev) => {
        if (prev >= targetWordCountRef.current) return prev
        return prev + 1
      })
      revealTimerRef.current = setTimeout(tick, 15)
    }
    tick()
    return () => {
      if (revealTimerRef.current) clearTimeout(revealTimerRef.current)
    }
  }, [streaming])

tick() is called directly (no initial setTimeout) so the first word reveals in the same frame streaming becomes true, not 35ms later. Subsequent ticks use 15ms instead of 35ms so more words reveal per second. Do not change the targetWordCountRef update effect, the render condition, the finally block reset, or any other part of the streaming or reveal logic. Do not touch any other file.

## VERIFY AFTER ACT

sed -n '150,163p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: tick() called directly with no initial delay, subsequent setTimeout uses 15ms.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask "where are my clients?" -- a short 1-2 sentence response.
3. Confirm the response now reveals word by word even on this short response.
4. Ask "how do I customize my client portal colors?" -- a longer bulleted response.
5. Confirm the reveal is still smooth on longer responses too, not too fast.
6. Ask both back to back and confirm clean reset between them.

Report what you observe at steps 3 and 5 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: word-reveal now fires immediately on streaming start with no initial delay, and ticks every 15ms instead of 35ms, so even short responses that complete quickly get a visible word-by-word reveal instead of appearing all at once"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.