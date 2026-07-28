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

TASK: Fix a real event-name collision where the new Billing banner prefill accidentally also overwrites the Concierge chat input on unrelated draft-to-Messages-tab actions

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '260,270p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '1078,1084p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '1470,1476p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "prefill-message" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Confirm three separate things currently share the exact same ConciergeAction type string, prefill-message: the two pre-existing dispatches inside ConciergePanel.tsx intended only for the client detail page's Messages tab compose box, and the new listener added earlier tonight inside ConciergePanel.tsx itself intended only for the Billing banner's hand-off into the main chat input. Confirm the event bus is a global window event, received by every mounted listener regardless of which component dispatched it, before editing.

WHAT THIS IS:

Confirmed by direct code reading: the Billing banner task added earlier tonight gave ConciergePanel.tsx a new listener for the prefill-message action type, intending to catch only the new banner's hand-off. But two pre-existing, unrelated dispatches of that exact same action type already existed in this same file, used specifically to pre-fill a draft into a client's Messages tab compose box on the client detail page, a completely different feature built earlier this session. Because the event system is a single global window event with no scoping by intended destination, ConciergePanel's new listener now also fires on those two pre-existing dispatches, silently overwriting the main Concierge chat input with draft content every time a user sends a notification draft to a client's Messages tab, an action completely unrelated to the Billing banner. This is a real, confirmed regression introduced by reusing an existing event name for a new, different purpose instead of introducing a new one.

CHANGE INSTRUCTIONS:

Add a new ConciergeAction type, prefill-panel-input, to the ConciergeAction interface in conciergeEvents.ts, alongside the existing prefill-message type, not replacing it.

In ConciergePanel.tsx's onConciergeAction listener, change the condition added earlier tonight from checking action.type === 'prefill-message' to checking action.type === 'prefill-panel-input', keeping the same setInput(action.prefillMessage) behavior.

In billing/page.tsx, change the banner's onAction callback to emit type prefill-panel-input instead of prefill-message for its second emitConciergeAction call. Do not change the first open-panel call.

Do not touch either of the two pre-existing prefill-message dispatches in ConciergePanel.tsx related to the Messages tab draft feature, and do not touch the client detail page's own prefill-message listener. These should continue working exactly as they did before tonight, completely unaffected by this change.

VERIFY AFTER ACT:

grep -n "prefill-panel-input\|prefill-message" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "prefill-panel-input\|prefill-message" /home/corby/jamm-os/frontend/src/app/\(app\)/billing/page.tsx

grep -n "prefill-message" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Expected: ConciergePanel.tsx now listens for prefill-panel-input specifically for the chat input, while still containing its two original, untouched prefill-message dispatches for the Messages tab feature. billing/page.tsx now emits prefill-panel-input. The client detail page's prefill-message listener is completely unchanged.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

On the Billing page, click the overdue invoices banner's action. Confirm the Concierge chat input still correctly gets pre-filled with the overdue invoices question.

Separately, trigger a notification draft's "open Messages tab with this draft ready to send" action from the Concierge panel's alert tray. Confirm the client's Messages tab compose box still correctly receives the draft, and confirm the Concierge chat's own main input is no longer affected by this action at all.

Report pass or fail for both checks individually, since the second check is the one confirming tonight's regression is actually fixed.

GIT:

git add -A

git commit -m "fix a real event-name collision between the Billing banner's chat-input prefill and the pre-existing Messages-tab draft prefill feature, both of which were using the same prefill-message ConciergeAction type on a global event bus, causing the Concierge chat input to be silently overwritten every time a notification draft was sent to a client's Messages tab, an unrelated action; introduced a distinct prefill-panel-input action type for the Billing banner's use case, leaving the original Messages tab feature completely untouched"

git pull --rebase origin main

git push origin main