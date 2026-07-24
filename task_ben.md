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

TASK: Redesign the client detail page and its four embedded tab components onto the token system, one coordinated visual unit

USE: Fable 5

VERIFY BEFORE ACT:
grep -c "bg-\[#\|text-\[#\|border-\[#" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx /home/corby/jamm-os/frontend/src/components/clients/IrsAuthTab.tsx /home/corby/jamm-os/frontend/src/components/clients/DocumentExpirySection.tsx /home/corby/jamm-os/frontend/src/components/clients/PortalPreview.tsx

Read all five files completely in full before changing anything. This is the single highest daily-traffic page in the entire application outside the Dashboard, carrying genuine business critical functionality: client contact information, engagement lists, document requests, IRS authorization status and expiry tracking, portal access and preview, notes, tax organizer data, and billing detail. This task must not touch any data fetching, any React Query usage, any state, any conditional logic, any API call, any function body, only visual presentation, class names, and static JSX structure. If unsure whether something is presentational or logical, treat it as logical and leave it untouched.

WHAT THIS IS:

Confirmed via a complete, systematic audit of the entire application: this page and its four embedded tab components, NotesPanel, IrsAuthTab, DocumentExpirySection, and PortalPreview, together account for roughly 207 hardcoded raw hex color values, meaning this entire page still looks exactly like the pre-redesign application while the Dashboard and Concierge panel have already been updated. Treating the parent page and its own tabs as one coordinated task is deliberate, fixing the page shell while leaving its own tabs on the old palette would simply move the inconsistency one click deeper rather than resolve it.

CHANGE INSTRUCTIONS:

Replace hardcoded hex values across all five files with the equivalent real design tokens already established and already proven on ConciergePanel.tsx and the Dashboard, brand, surface, dark, status, concierge where contextually appropriate, and font-sans, font-display.

Apply the display serif specifically to the client's name as the page's main heading, and to any key figures shown on this page such as outstanding balances, invoice amounts, or engagement counts, matching the same treatment already established for key figures elsewhere.

Give the tab navigation, cards, and panels on this page the same real visual separation and elevation treatment already established on the Dashboard, rather than the current flat, barely distinguished boundaries.

Ensure the IrsAuthBadge and StatusBadge components, and any status-driven color coding such as overdue, active, or expiring soon indicators, continue to use the correct semantic status tokens and remain immediately distinguishable by color, this information genuinely needs to stay scannable at a glance, do not let a broad token migration accidentally flatten meaningful status color distinctions into visually identical tones.

Do not change any prop, any function, any API call, any React Query key or configuration, any conditional rendering logic, any state variable, in any of the five files. Every single change in this task must be limited to className strings, static JSX text for non-dynamic labels, and the addition of the font-display utility class, nothing else.

VERIFY AFTER ACT:

grep -c "bg-\[#\|text-\[#\|border-\[#" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx /home/corby/jamm-os/frontend/src/components/clients/IrsAuthTab.tsx /home/corby/jamm-os/frontend/src/components/clients/DocumentExpirySection.tsx /home/corby/jamm-os/frontend/src/components/clients/PortalPreview.tsx

Expected: dramatically lower across all five files, ideally at or near zero in each.

npm run build in frontend, expected zero TypeScript errors.

Explicitly confirm, by direct comparison of the relevant code before and after, that every React Query hook, every API call, every prop passed into NotesPanel, IrsAuthTab, DocumentExpirySection, and PortalPreview, and every conditional branch remain byte for byte unchanged. Paste this confirmation explicitly, do not simply assert it.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

Open a real client's detail page in light mode. Confirm the page now visually matches the warm palette and typography already established elsewhere, no longer reading as a different, older product. Switch to dark mode, confirm the same and confirm full readability throughout, including inside every tab.

Click through every tab on this page individually, Overview, Notes, IRS Authorizations, Documents, Portal, and confirm each one still displays real, correct data exactly as before, and confirm no interactive element, button, or form within any tab is broken or non-functional.

Specifically confirm status indicators, an overdue or expiring IRS authorization, an active engagement, remain immediately visually distinguishable by color, not flattened into indistinguishable tones by the token migration.

Confirm creating or viewing a note, if testable, still works correctly. Confirm the portal preview still renders correctly. Confirm opening a new engagement modal from this page, if present, still works correctly.

Report pass or fail individually for light mode, dark mode, each tab's data accuracy, status color distinguishability, and functional interactivity, with screenshots of at least three different tabs in both light and dark mode.

GIT:
git add -A
git commit -m "redesign the client detail page and its four embedded tab components, notes, IRS authorizations, document expiry, and portal preview, onto the established token system and typography as one coordinated unit, since this is the highest daily traffic page in the application outside the Dashboard, with zero changes to any data fetching, state, or interactive logic across all five files"
git pull --rebase origin main
git push origin main