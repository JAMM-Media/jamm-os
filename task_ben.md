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

# Task: Decouple word-reveal timer from messages array to fix choppy reveal during active line bursts

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '142,162p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current reveal useEffect has dependency array [streaming, messages], and that the tick chain is fully torn down (clearTimeout) and rebuilt from scratch every time this effect re-runs.

## WHAT IS WRONG

Confirmed via live testing and direct code inspection: the word-reveal effect depends on the full messages array. Since messages is a new array reference every time a backend line arrives (the existing incremental setMessages call from commit f9f7def), React tears down and restarts the entire reveal tick chain on every single line arrival, not just once per streaming session. Early in a response, lines often arrive in quick succession (e.g. several short headers or bullets close together), faster than the 35ms reveal tick. Each new arrival resets the countdown before the previous tick ever fires, so almost nothing gets visually revealed during these bursts. This produces a choppy, frozen-feeling first few seconds, followed by smooth reveal once line arrivals space out past 35ms apart and the tick chain can finally run uninterrupted.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Replace the reveal effect so the ticking timer is only created once when streaming starts, and reads the current target word count from a ref that updates separately, rather than tearing down the timer on every content change.

Add a ref to hold the latest target word count:

  const targetWordCountRef = useRef(0)

Add a lightweight effect that only updates this ref when messages changes, with no timer logic in it at all:

  useEffect(() => {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg && lastMsg.role === 'concierge') {
      targetWordCountRef.current = lastMsg.content.split(/\s+/).filter(Boolean).length
    }
  }, [messages])

Replace the existing reveal effect so it depends only on streaming, starting the tick chain once and never tearing it down due to content changes:

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

This means the tick chain starts exactly once per streaming response and runs continuously at a steady 35ms cadence regardless of how quickly or slowly lines arrive from the backend, always reading the most current target word count via the ref rather than a stale closure. Do not change the snap-to-end logic (setRevealedWordCount(Number.MAX_SAFE_INTEGER) after streaming completes), the word-reset on new message start, or the conditional render slice. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "targetWordCountRef" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: the ref declaration, the lightweight update effect, and its use inside tick() are all present.

grep -n "\[streaming, messages\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: no longer present -- the reveal effect's dependency array should now read [streaming] only.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask "can I see the morning briefing again?" again, the same test case that revealed the choppy start.
3. Confirm the reveal now feels steady and consistent from the very first word, with no noticeably choppy or frozen period at the start before it smooths out.
4. Confirm the rest of the behavior is unchanged: smooth reveal throughout, no broken markdown mid-reveal, and a clean snap to full content once streaming completes.

Report what you observe at step 3 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: word-reveal timer no longer restarts on every backend line arrival, decoupling it from the messages array so the reveal cadence stays steady from the start instead of choppy during early bursts of fast-arriving lines"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.