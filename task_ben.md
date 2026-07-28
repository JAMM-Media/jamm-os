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

TASK: Add a SuggestionCard to the client detail page's Overview tab for clients who have never been sent a portal invite, wired into tonight's already-hardened portal-magic-link flow

USE: Fable 5

VERIFY BEFORE ACT:

grep -n "portal_invite_sent_at" /home/corby/jamm-os/app/models/client.py

grep -n "portal_invite_sent_at" /home/corby/jamm-os/app/schemas/client.py

sed -n '124,131p' /home/corby/jamm-os/app/schemas/client.py

sed -n '83,118p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

grep -n "'open-panel'" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

sed -n '1,25p' /home/corby/jamm-os/frontend/src/components/concierge-inline/SuggestionCard.tsx

Confirm portal_invite_sent_at exists as a nullable datetime field on the Client model but is currently absent from ClientOut, meaning it is not currently returned to the frontend at all. Confirm the client detail page already has a working live onConciergeAction listener that correctly handles a navigate-and-open action with modal portal-magic-link, setting the active tab to overview, setting portalLinkHighlight true, scrolling the button into view, and clearing the highlight after 7000ms, fixed and verified earlier tonight. Confirm open-panel is handled in AppShell.tsx, which owns the conciergeOpen boolean passed into ConciergePanel as isOpen. Confirm SuggestionCard's real prop shape from the Phase 1 kit before using it. Confirm all of this before making any change.

WHAT THIS IS:

This is the second real, live page of the inline Concierge redesign, following the Billing overdue-invoices banner built and verified earlier tonight. This one is lower risk in one specific way: instead of building a new hand-off mechanism, it reuses the portal-magic-link action pipeline that this session already spent significant effort hardening end to end tonight, the modal string match, the never-claim-completed phrasing rule, the ampersand-safe client name resolution, the hydration fix, the missing mount-time branch fix, and the 7 second highlight duration. The only new thing this task adds is a real, visible entry point into that already-proven pipeline, directly on the client detail page itself, for any client who has never been sent a portal invite at all, which is not something the product currently surfaces anywhere.

CHANGE INSTRUCTIONS:

Backend: add portal_invite_sent_at as an optional datetime field to ClientOut in schemas/client.py, matching the exact type and style of the other optional fields already present. Do not add any new endpoint, this field will now simply be included automatically in the existing GET /clients/{id} response already used by this page. Do not change the Client model itself, it already has this field, only expose it.

Frontend: on the client detail page's Overview tab, when the fetched client's portal_invite_sent_at is null, render a SuggestionCard above the existing content, using the concierge-inline kit's real prop shape, with a message stating this client has not been sent a portal invite yet, and a primary action labeled something like Send portal invite. The onAction callback should call emitConciergeAction twice in sequence, first with type open-panel, then with type navigate-and-open, route set to this client's own current route, and modal set to portal-magic-link, exactly matching the shape the model itself already emits for this action, so this reuses the exact same, already-fixed live listener path on this page rather than introducing any new logic. Do not write any new highlight, tab-switching, or scrolling logic in this task, all of that already exists and already works. Do not change the SuggestionCard component itself unless its existing props genuinely cannot express this use case, in which case state clearly what was missing before extending it.

VERIFY AFTER ACT:

grep -n "portal_invite_sent_at" /home/corby/jamm-os/app/schemas/client.py

grep -n "SuggestionCard" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

grep -n "portal-magic-link" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Expected: portal_invite_sent_at now present in ClientOut, SuggestionCard now imported and rendered conditionally, and a third occurrence of portal-magic-link now exists on this page in addition to the two already confirmed earlier tonight.

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

Find or create a client whose portal_invite_sent_at is null, confirm the SuggestionCard appears on their Overview tab with the correct message.

Click the card's action. Confirm the panel opens, switches to Overview if not already there, and the portal-link button highlights for the full 7 seconds, matching the already-verified behavior from earlier tonight.

Separately, open a client who has already been sent a portal invite, confirm the SuggestionCard does not appear for them.

Report pass or fail for all three checks individually.

GIT:

git add -A

git commit -m "add the second real page of the inline Concierge redesign, a SuggestionCard on the client detail page's Overview tab for clients who have never been sent a portal invite, wired directly into the already-hardened portal-magic-link action pipeline built and verified earlier tonight rather than introducing any new hand-off logic, and expose the previously backend-only portal_invite_sent_at field on ClientOut so the frontend can read it"

git pull --rebase origin main

git push origin main