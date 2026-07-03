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

# Task: Add Clear Conversation button, stop auto-wiping conversation on panel close

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n 'if (!isOpen)' -A 10 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current close-effect: on close, it resets autopilot, clears jamm_concierge_autopilot and jamm_concierge_messages from sessionStorage, calls setMessages([]), and sets hasInitialized.current = false.

sed -n '845,882p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the exact header structure: the Autopilot toggle button, then the Close (X) button, both inside a flex container with gap-2.

grep -n "from 'lucide-react'" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current icon import line, so Trash2 can be added to it.

## WHAT IS WRONG

Closing the Concierge panel (clicking X) currently wipes the entire conversation automatically and irreversibly, with no way to keep it or bring it back. This was flagged as the wrong default -- closing the panel is often just "I'm done looking at this for now," not "delete everything I just discussed." The fix is twofold: stop clearing the conversation automatically on close (the conversation should persist until the user explicitly clears it), and add a small, explicit Clear Conversation icon in the panel header that the user can click when they genuinely want to start fresh, with a confirmation step since this action is irreversible. The button should only appear once there is an actual conversation to clear (more than just the initial opening message), not on every fresh empty panel.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Step 1: Update the icon import to add Trash2:

import { X, Send, Zap, Download, ChevronDown, Trash2 } from 'lucide-react'

Step 2: Update the close-effect to stop wiping the conversation, keeping only the autopilot reset and the hasInitialized reset (which is still needed so the opening flow correctly re-evaluates on the next open):

    if (!isOpen) {
      setAutopilotOn(false)
      autopilotRef.current = false
      sessionStorage.removeItem('jamm_concierge_autopilot')
      hasInitialized.current = false
    }

Remove sessionStorage.removeItem('jamm_concierge_messages') and setMessages([]) from this block -- the conversation now persists across a close/reopen cycle within the same browser session, exactly as it already does across page navigation.

Step 3: Add a handler function for clearing the conversation, placed near the other handler functions in the component:

  function handleClearConversation() {
    const confirmed = window.confirm('Clear this conversation? This cannot be undone.')
    if (!confirmed) return
    setMessages([])
    sessionStorage.removeItem('jamm_concierge_messages')
    setSuggestions([])
  }

Step 4: Add the Clear Conversation button in the header, positioned between the Autopilot toggle and the Close button, only rendered when there is more than just an initial single message:

Insert this new button inside the header's flex container (the div with className="flex items-center gap-2" that currently holds the Autopilot toggle and the Close button), after the Autopilot toggle's closing </div> and before the existing Close button:

            {messages.length > 1 && (
              <button
                onClick={handleClearConversation}
                aria-label="Clear conversation"
                title="Clear conversation"
                className="text-[#6B7280] hover:text-[#DC2626] dark:hover:text-[#F87171] transition-colors"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}

The messages.length > 1 condition hides the button when only the initial opening message is present (morning briefing, cooldown message, or plain opener), showing it only once a real back-and-forth exists.

Do not change any other part of the header, the Autopilot toggle's own logic, or any other section of this file.

## VERIFY AFTER ACT

grep -n "Trash2" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present in the import line and in the new button.

grep -n "handleClearConversation" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: the function definition and its use in the new button's onClick, both present.

grep -n "setMessages(\[\])" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: no longer present inside the close-effect (the if (!isOpen) block) -- only present now inside handleClearConversation.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open the Concierge panel, ask a real question, get an answer. Confirm the Clear Conversation icon now appears in the header (it should not have been visible before this exchange, only the initial opening message).
3. Close the panel (X button), then reopen it. Confirm the conversation from step 2 is still there, not wiped -- this is the core behavior change.
4. Click the new Clear Conversation icon. Confirm a browser confirm dialog appears asking to confirm.
5. Cancel the dialog, confirm the conversation is untouched.
6. Click the icon again and confirm this time. Confirm the conversation is now cleared, back to a blank state with no messages and no leftover suggestion chips.
7. Regression check: confirm Autopilot still correctly resets to off when the panel is closed (unrelated to the conversation-clearing change, should be unaffected).
8. Regression check: navigate between pages (not closing the panel) and confirm the conversation still persists across navigation exactly as it did before this task, since Phase 1/2 persistence logic was not touched.

Report what you observe at steps 3, 4, and 6 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: Concierge conversation now persists across closing and reopening the panel instead of being automatically wiped, and a new Clear Conversation icon in the header lets the user explicitly clear it when they want to, with a confirmation step since the action is irreversible. The button only appears once a real conversation exists, not on the initial opening message alone."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.