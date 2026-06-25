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

# Task: Combine cooldown messaging, clean re-request phrasing, and enable the download button when the briefing is shown again

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "Already checked in with your morning briefing" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the exact current cooldown message line.

sed -n '590,630p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the existing CONCIERGE_ACTION pattern: ACTION_MARKER parsing in handleConciergeAction, the special-cased set_firm_type type that routes through pendingActionRef and bypasses the normal autopilotRef.current gate (unlike other action types, which require Autopilot ON before they execute), and how executeAction dispatches on action.type.

grep -n "isBriefing\|detailReady\|detailBriefing" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm how the original morning-briefing open flow sets isBriefing: true on a message and populates detailBriefing/detailReady to enable the Download briefing button, so the new action type can reproduce this exactly.

grep -n "morning briefing\|briefing again" /home/corby/jamm-os/app/api/concierge/prompts.py -i

Find any existing instruction governing how the model responds when a user asks to see the briefing again, to edit in place rather than duplicate.

## WHAT IS WRONG

Three related, confirmed issues around re-requesting the morning briefing after it has already run today:

1. The cooldown fallback message does not tell the user they can ask to see the briefing again, so a user who dismissed it or missed it has no obvious path to retrieve it.
2. When a user does ask, the model's response repeats itself awkwardly ("Here is your briefing again. Here is your morning briefing.").
3. Critically, asking to see the briefing again returns a normal chat message with no Download briefing button, because that capability only exists on the message created by the original _open() flow, which sets isBriefing: true and populates detailBriefing/detailReady. A re-requested briefing goes through the generic /concierge/chat path instead, which never sets any of this, so the user cannot download a briefing they explicitly asked to see again.

## ACTION

File 1: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Update the cooldown message:

"Already checked in with your morning briefing earlier today. Ask me anytime if you'd like to see it again, or let me know if anything's changed or if you need help with something specific."

In handleConciergeAction, add a new special-cased action type following the exact same pattern as set_firm_type (bypassing the autopilotRef.current gate, since this is a read action, not a navigation or automation action that should require Autopilot ON):

      if (action.type === 'set_firm_type') {
        pendingActionRef.current = action
        return beforeAction || ''
      }
      if (action.type === 'show_briefing_again') {
        pendingActionRef.current = action
        return beforeAction || ''
      }

In executeAction, add a new branch handling this type, fetching the detail briefing and attaching it to the most recent concierge message exactly the way the original open flow does:

    if (action.type === 'show_briefing_again') {
      try {
        const res = await api.post('/concierge/morning-briefing/detail')
        if (res.status === 200 && res.data?.briefing) {
          setDetailBriefing(res.data.briefing)
          setDetailReady(true)
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'concierge') {
              updated[updated.length - 1] = { ...last, isBriefing: true }
            }
            return updated
          })
        }
      } catch {
        // non-fatal -- message text already shown, download button simply will not appear
      }
      return
    }

File 2: /home/corby/jamm-os/app/api/concierge/prompts.py

Add or adjust an instruction covering this exact case, near the existing morning briefing or DRAFT RESPONSE PATTERNS section, in the same voice as the rest of the file:

When a user asks to see the morning briefing again after it has already been shown today, respond with one clean lead-in sentence such as "Here's your briefing again:" followed by the briefing content. Do not repeat the phrase "morning briefing" or restate the lead-in a second time. After the briefing content, emit CONCIERGE_ACTION: {"type":"show_briefing_again"} on its own line so the download option becomes available again.

Do not change the cooldown duration, the original _open() morning-briefing flow, or any other message or action type in either file.

## VERIFY AFTER ACT

grep -n "show_briefing_again" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present in both files.

grep -n "Ask me anytime if you'd like to see it again" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart both backend and frontend.
2. Trigger the cooldown state (open the panel a second time today after a real briefing already ran) and confirm the message mentions it can be requested again.
3. Ask "can I see the morning briefing again?" and confirm the response leads with one clean sentence, no repeated stutter phrasing.
4. Confirm a Download briefing button now appears on this re-requested message, and clicking it successfully downloads a PDF, exactly as it does on the very first open of the day.
5. Regression check: confirm the original first-open-of-the-day flow (real briefing, Download button, detail fetch) still works exactly as before, unaffected by this change.
6. Regression check: confirm Autopilot does not need to be turned on for the download button to appear on a re-request, since this is a read action and should not require it, same as set_firm_type does not require it.

Report what you observe at steps 3, 4, and 6 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: re-requesting the morning briefing now produces clean non-repetitive phrasing and restores the Download briefing button, instead of returning plain chat text with no way to download a briefing the user explicitly asked to see again"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.