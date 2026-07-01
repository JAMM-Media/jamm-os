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

# Task 1: Fix glitchy word-reveal on longer responses by switching from setTimeout to requestAnimationFrame

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '150,163p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current reveal useEffect uses setTimeout(tick, 15) for the recursive interval with tick() called directly for the first tick.

## WHAT IS WRONG

Confirmed via live testing: short responses now reveal correctly word by word, but longer responses (multi-line, bulleted) show a glitchy freeze mid-reveal. Root cause: setRevealedWordCount fires via setTimeout every 15ms, independent of the browser's render cycle. At this rate (~67 state updates per second), React re-renders the message bubble on every tick, which includes re-parsing the growing word-sliced string through ReactMarkdown on every single update. ReactMarkdown is not cheap -- it parses markdown syntax on every render -- and at 67 renders per second during a long response it causes the observable freeze/stutter. requestAnimationFrame syncs state updates to the browser's natural 60fps paint cycle (~16ms), coordinates with React's own scheduler, and prevents intermediate renders that never appear on screen, eliminating the stutter without changing the visual feel.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Change revealTimerRef from ReturnType<typeof setTimeout> to number to match requestAnimationFrame's return type:

  const revealTimerRef = useRef<number | null>(null)

Replace the reveal useEffect body to use requestAnimationFrame instead of setTimeout:

  useEffect(() => {
    if (!streaming) return
    function tick() {
      setRevealedWordCount((prev) => {
        if (prev >= targetWordCountRef.current) return prev
        return prev + 1
      })
      revealTimerRef.current = requestAnimationFrame(tick)
    }
    revealTimerRef.current = requestAnimationFrame(tick)
    return () => {
      if (revealTimerRef.current) cancelAnimationFrame(revealTimerRef.current)
    }
  }, [streaming])

Note: tick() is now called via requestAnimationFrame(tick) for the first frame rather than directly, since requestAnimationFrame already fires on the next paint which is effectively immediate. The cleanup uses cancelAnimationFrame instead of clearTimeout. Do not change the targetWordCountRef update effect, the render condition, the finally block reset, or any other part of the streaming or reveal logic. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "requestAnimationFrame\|cancelAnimationFrame" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: requestAnimationFrame used for both the recursive call and the initial call, cancelAnimationFrame used in cleanup.

grep -n "setTimeout.*tick\|clearTimeout.*reveal" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: no matches -- setTimeout is completely replaced.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask "how do I customize my client portal colors?" -- the longer bulleted response that showed the freeze.
3. Confirm the reveal is now smooth with no visible freeze or stutter mid-response.
4. Ask "where are my clients?" -- confirm short responses still reveal word by word.
5. Ask both back to back -- confirm clean reset between them.

Report what you observe at steps 3 and 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: word-reveal now uses requestAnimationFrame instead of setTimeout to sync with the browser paint cycle and eliminate the glitchy freeze on longer responses caused by too many ReactMarkdown re-renders per second"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.