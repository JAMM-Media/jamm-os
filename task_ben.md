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

TASK: Fix the last two real findings from tonight's final launch-readiness audit -- a stale-route bug preventing modals from opening after navigation, and confusing wording when portal access and portal invite status disagree

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '838,860p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '138,145p' /home/corby/jamm-os/app/api/concierge/route.py

grep -n "portal_access\|portal access" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the generic route-plus-modal branch in executeAction, the one used for actions like navigate-and-open with route /clients and modal new-client, currently calls router.push(normalizedRoute) unconditionally first, then separately computes alreadyOnRoute using pathname.startsWith(normalizedRoute), a prefix match rather than an exact match. Confirm this means being on any sub-route beginning with /clients, such as a specific client's own detail page, incorrectly satisfies this check for the plain /clients list route, causing the action to be dispatched live into a page that is mid-navigation-away instead of being safely persisted for the new page to read after it mounts. Confirm the real, current wording of get_client_full_snapshot's tool description, and confirm whether prompts.py currently has any guidance on reconciling portal_access_enabled and portal_invite_sent_at when they present a seemingly contradictory picture.

WHAT THIS IS:

Two real, separately confirmed findings from a final, broad pre-launch audit tonight. First, asking the Concierge to create a new client while on a page other than the exact Clients list page, for example a specific client's own detail page, correctly navigates to Clients but the New Client form never actually opens, because the stale pathname check at the moment of navigation is a prefix match rather than an exact match, causing this specific case to take the wrong internal branch. Second, the Concierge told the truth about two real, different fields, portal_access_enabled and portal_invite_sent_at, for a client where these two facts point in different directions, but stated only one of them, portal access enabled, without acknowledging the invite itself was never sent, reading as a contradiction next to the on-page suggestion card that already correctly flags the missing invite. This is not a fabrication, both facts are real, it is a clarity gap worth closing before launch.

CHANGE INSTRUCTIONS:

In ConciergePanel.tsx's executeAction, in the generic route-plus-modal branch, change the alreadyOnRoute check from pathname.startsWith(normalizedRoute) to an exact match, pathname === normalizedRoute, so only being litarally on the exact target route counts as already there, not any sub-route beginning with the same path segment. Do not change the client-slug-specific branch earlier in this function, and do not change any other logic in executeAction.

In prompts.py, add a short, specific instruction near or within the general formatting or tool-use guidance, stating that when a client snapshot shows portal_access_enabled as true but portal_invite_sent_at is null or absent, the response must state both facts together, for example noting that portal access is enabled for the client but they have not yet been sent their actual invite link, rather than stating only one of these two real facts in isolation, since doing so can read as contradictory next to other parts of the product that correctly surface the missing invite.

VERIFY AFTER ACT:

grep -n "pathname === normalizedRoute" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "portal_access_enabled\|portal access is enabled" /home/corby/jamm-os/app/api/concierge/prompts.py

npx tsc --noEmit

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart both servers.

While on a specific client's detail page, not the Clients list page, ask the Concierge to create a new client. Confirm it navigates to the Clients page and the New Client form now actually opens, not just the correct wording claiming it would.

Ask the Concierge to tell you about Robert & Carol Tanner again. Confirm the response now explicitly reconciles both facts, mentioning that portal access is enabled but the invite itself has never been sent, rather than stating only one of these two real facts.

Confirm asking to create a new client while already on the exact Clients list page still works exactly as it did before, unaffected by this change.

Report pass or fail for each of these three checks individually.

GIT:

git add -A

git commit -m "fix the last two real findings from tonight's final pre-launch audit: correct a stale-route bug in executeAction where a prefix match on the current pathname incorrectly treated being on any client sub-route as already being on the plain Clients list page, causing the New Client modal to silently never open after navigating there from elsewhere, now fixed to an exact route match; and add explicit guidance so the Concierge states both portal_access_enabled and portal_invite_sent_at together when they present a seemingly contradictory picture, rather than stating one real fact in isolation in a way that reads as inaccurate next to other correct parts of the product"

git pull --rebase origin main

git push origin main