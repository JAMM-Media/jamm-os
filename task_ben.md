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

# Task: Reset hasInitialized ref on panel close so reopening correctly re-triggers the opening flow

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "hasInitialized" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm hasInitialized is a useRef(false), set to true at the start of the isOpen-driven _open effect, and never reset to false anywhere in the file, including the existing close-effect that already wipes messages back to an empty array.

grep -n "if (!isOpen)" -A 8 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the existing close-effect: when isOpen becomes false, it resets autopilotOn, clears jamm_concierge_autopilot and jamm_concierge_messages from sessionStorage, and calls setMessages([]) -- but does not touch hasInitialized.

## WHAT IS WRONG

Confirmed via live testing: closing and reopening the Concierge panel within the same browser session produces a completely empty panel, no welcome message, no morning briefing, no onboarding question, nothing -- just the bare starter-prompt suggestion chips with no preceding message bubble at all.

Root cause: hasInitialized is a ref set to true the first time the panel ever opens in a session, and it is never reset. The opening effect's guard, if (isOpen && !hasInitialized.current), is permanently false after the very first open. Meanwhile, the existing close-effect already wipes messages back to an empty array when the panel closes. The combination means every reopen after the first close starts with messages.length === 0 (so the empty starter-prompts state renders) but the opening logic that would normally populate that first message never re-runs, because hasInitialized.current still reads true from the original open. This affects every code path inside _open: the morning briefing call, the cooldown message just added, the firm_type onboarding question, and the plain __OPEN__ sentinel message -- all of it silently skipped on every reopen, not just specific to today's testing.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

In the existing close-effect (the one already resetting autopilotOn and clearing messages when isOpen becomes false), add a reset of hasInitialized.current:

  useEffect(() => {
    if (!isOpen) {
      setAutopilotOn(false)
      autopilotRef.current = false
      sessionStorage.removeItem('jamm_concierge_autopilot')
      sessionStorage.removeItem('jamm_concierge_messages')
      setMessages([])
      hasInitialized.current = false
    }
  }, [isOpen])

This ensures that the next time the panel opens, the guard at if (isOpen && !hasInitialized.current) is true again, and the full opening flow (morning briefing check, cooldown message, onboarding question, or __OPEN__ sentinel) correctly re-runs, exactly as it does on a true first-ever open. Do not change the morning-briefing cooldown logic itself, the redundant hasInitialized.current = true assignments inside the briefing branches (they remain correct and harmless), or any other section of this file. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "hasInitialized.current = false" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present, inside the close-effect.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open the Concierge panel on the dashboard, confirm the opening message appears (either a real briefing, the cooldown message, or the plain opening message, depending on current cooldown state -- any of these is fine for this test, the point is that something appears, not which one).
3. Close the panel.
4. Reopen the panel again on the same dashboard page, in the same browser session, without reloading the page.
5. Confirm an opening message appears again this time too, instead of the bare empty starter-prompts state with no message at all.
6. Repeat close and reopen a third time to confirm this is reliably fixed, not a one-off.
7. Regression check: send a few chat messages, close the panel, reopen it, and confirm the previous conversation does NOT incorrectly persist if that is not the intended behavior -- note this only if it behaves unexpectedly, since the existing close-effect already intentionally clears messages and sessionStorage on close, and that part is not being changed here.

Report what you observe at steps 5 and 6 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge panel hasInitialized ref now resets on close, so reopening the panel within the same session correctly re-triggers the opening flow (morning briefing, cooldown message, onboarding question, or plain opener) instead of silently showing an empty panel with no message at all"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.