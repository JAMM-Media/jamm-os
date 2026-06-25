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

# Task: Distinguish morning briefing cooldown from a real failure, so the fallback message is honest about which happened

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '878,917p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm the current morning_briefing handler: the cooldown check returning Response(status_code=204) when briefing_sent_at is under 64800 seconds old, and the separate except block also returning Response(status_code=204) on a real failure. Both currently return the exact same response shape, so the frontend cannot tell them apart.

grep -n "pathname.startsWith('/dashboard')" -A 20 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current frontend _open logic: it calls /concierge/morning-briefing, checks for res.status === 200 && res.data?.briefing, and on anything else falls through silently to the firm_type check and then the generic __OPEN__ message, with no distinction made for why the briefing did not come back.

## WHAT IS WRONG

Confirmed via live testing and direct backend log inspection: the morning briefing endpoint has a deliberate 18-hour cooldown (64800 seconds) so it does not regenerate a new briefing every time the panel opens. This is correct, intentional behavior, not a bug. However, when the cooldown is active, the endpoint returns the exact same 204 No Content response as when a real failure occurs (an exception during the Anthropic call, caught and logged as a warning). The frontend cannot distinguish "intentionally skipped, already briefed today" from "something actually broke," so both cases produce the same generic fallback message with no acknowledgment that a real briefing already happened earlier.

## ACTION

File 1: /home/corby/jamm-os/app/api/concierge/route.py

In the cooldown branch, change the response to be distinguishable from the failure branch:

    if current_firm.briefing_sent_at is not None:
        elapsed = (datetime.now(timezone.utc) - current_firm.briefing_sent_at).total_seconds()
        if elapsed < 64800:
            return JSONResponse({"cooldown": True}, status_code=200)

Leave the except block's return Response(status_code=204) for real failures exactly as is, so genuine errors remain distinguishable as a non-200 response. Do not change the cooldown duration, the AutomationRule check, or the try block's success path. Do not touch any other function in this file.

File 2: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

In the _open function's dashboard branch, add a check for the cooldown signal before falling through to the firm_type check:

              const res = await api.post('/concierge/morning-briefing')
              if (res.status === 200 && res.data?.briefing) {
                setMessages([{ role: 'concierge', content: res.data.briefing, isBriefing: true }])
                api.post('/concierge/morning-briefing/detail')
                  .then((r) => { if (r.data?.briefing) { setDetailBriefing(r.data.briefing); setDetailReady(true) } })
                  .catch(() => {})
                hasInitialized.current = true
                setBriefingLoading(false)
                return
              }
              if (res.status === 200 && res.data?.cooldown) {
                setMessages([{ role: 'concierge', content: "Already checked in with your morning briefing earlier today. Let me know if anything's changed or if you need help with something specific." }])
                hasInitialized.current = true
                setBriefingLoading(false)
                return
              }

Place this directly after the existing briefing success check, before the existing try block closes. Do not change the existing success branch. Do not change the catch block or the fallback to the firm_type check, which should still run for genuine failures (non-200, non-cooldown responses). Do not touch any other section of this file.

## VERIFY AFTER ACT

grep -n "cooldown" /home/corby/jamm-os/app/api/concierge/route.py /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present in both files.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart both backend and frontend.
2. Open the dashboard fresh (private window or cleared sessionStorage) and confirm a real morning briefing loads normally on the first open of the day, exactly as before.
3. Close the panel, then reopen it again within the same day (a second fresh session, same firm) and confirm this time the message reads "Already checked in with your morning briefing earlier today..." instead of the generic "Let's get ready to work" fallback.
4. Regression check: if possible, simulate a real failure (e.g. temporarily break the Anthropic API key, or note that this cannot be easily forced and just confirm via code review that the except block's 204 path is unchanged) and confirm that case still correctly falls through to the generic fallback message, not the cooldown message.

Report what you observe at step 3 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: morning briefing cooldown now returns a distinguishable response from a real failure, so the Concierge shows an honest 'already checked in today' message instead of the same generic fallback used for actual errors"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.