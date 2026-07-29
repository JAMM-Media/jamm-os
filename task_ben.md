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

TASK: Redesign SuggestionCard's visual treatment to match the "glanceable, honest, information-first" pattern, de-emphasizing its action button

USE: claude sonnet

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/SuggestionCard.tsx

sed -n '440,465p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Confirm SuggestionCard currently uses a left-side color stripe (border-l-[3px] border-l-concierge) rather than a full ring around the card, has no honest low-commitment label above the message, and renders its action button at full visual weight, the same bold concierge-colored fill as its identity dot. Confirm actionLabel and onAction are already optional, meaning a pure information, no-button card is already possible today by simply not passing them. Confirm the one real, live usage of this component, the client detail page's portal-invite card, before editing.

WHAT THIS IS:

Direct product decision, refining the SuggestionCard pattern first built earlier this session. The reference point is the "Maybe Important" pattern from Apple's own lock-screen AI notifications: a soft gradient ring around the card's edge, an honest, low-commitment label signaling this might be worth noticing rather than a command, and the actual content as the real headline. The decision made was to keep the action button rather than remove it entirely, since JAMM PX's Concierge has real, specific next steps to offer that a generic OS notification does not, but to visually de-emphasize it so the information itself reads as the primary element and the button reads as a quiet, secondary option, not the loudest thing on the card.

CHANGE INSTRUCTIONS:

Replace the left-side border stripe with a full, soft ring around the entire card, using the concierge token at a low opacity, for example a ring-1 with the concierge color at roughly 30 to 40 percent opacity, removing the border-l-[3px] treatment entirely. Keep the existing header bar with the dot and JAMM CONCIERGE label and dismiss button exactly as they are.

Add a new optional prop, honestLabel, a short string defaulting to "Might be worth a look" when not provided. Render it as a small, muted line directly above the message text, visually distinct from and smaller than the message itself.

Reduce the visual weight of the action button when present: change it from a solid concierge-colored fill to a lighter treatment, for example an outlined or ghost-style button using the concierge color for its text and border rather than as a solid background fill, and reduce its font weight or size slightly relative to the message text above it, so the information is clearly the primary element and the button is clearly secondary.

Update the one real usage of this component, the client detail page's portal-invite card, passing an honestLabel value if the default does not fit this specific case, otherwise leave it using the new default.

Do not change onDismiss behavior, and do not add any new required props, everything new must be optional with a sensible default so this remains a safe, backward compatible change.

VERIFY AFTER ACT:

grep -n "honestLabel\|ring-concierge\|border-l-\[3px\]" /home/corby/jamm-os/frontend/src/components/concierge-inline/SuggestionCard.tsx

Expected: honestLabel present, ring-concierge present, border-l-[3px] absent.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Visit the dev review route (/dev/concierge-kit) and confirm SuggestionCard now shows a full soft ring instead of a left stripe, in both light and dark mode.

Confirm the honest label appears above the message text, using the default text when not explicitly set.

Confirm the action button is now visibly smaller and quieter than the message text, not the loudest element on the card.

Visit a client old enough to trigger the real portal-invite card (for example Robert & Carol Tanner), confirm the real, live card reflects all of the same changes correctly.

Report pass or fail for each of the four checks individually.

GIT:

git add -A

git commit -m "redesign SuggestionCard's visual treatment: replace the left-side color stripe with a full soft ring around the card, add an optional honestLabel prop defaulting to 'Might be worth a look' for a low-commitment framing above the message, and de-emphasize the action button's visual weight so the information itself reads as the card's primary element, keeping the button rather than removing it since this Concierge has real, specific next steps a generic OS notification pattern does not"

git pull --rebase origin main

git push origin main