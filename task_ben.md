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

TASK: Give SuggestionCard a real, visible glow instead of a barely-perceptible ring, and fix the portal-invite card's button label to stop restating the always-visible Send Portal Link button

USE: claude sonnet

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/SuggestionCard.tsx

sed -n '443,462p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Confirm SuggestionCard currently uses ring-1 ring-concierge/30 with no glow/shadow effect, and confirm the client detail page's portal-invite card currently passes actionLabel="Send portal invite", the same wording as the always-visible Send Portal Link button rendered just below it on the same page. Confirm this before editing.

WHAT THIS IS:

Direct, live feedback tonight on the real, live portal-invite card: the ring is too subtle to read as intentional, nothing like the soft visible glow from the Apple reference image discussed earlier, and the button label "Send portal invite" still reads as a duplicate of the always-visible "Send Portal Link" button directly below it on the same page, even after the earlier fix that made the card only appear for genuinely aged, unnoticed clients. The card's actual behavior has never been to send anything itself, its onAction only opens the panel and highlights the real button, so its label should describe that, not restate the destination button's own wording.

CHANGE INSTRUCTIONS:

In SuggestionCard.tsx, add a real, soft glow effect to the card, using a box-shadow in the concierge color at low opacity, layered with the existing ring, for example combining ring-1 ring-concierge/40 with a shadow-[0_0_16px_rgba(191,150,64,0.35)] or equivalent Tailwind arbitrary value, tuned so the glow is genuinely visible at a glance in both light and dark mode without being harsh or oversaturated. Confirm the concierge token's real hex value before hardcoding an rgba value, rather than guessing.

On the client detail page, change the portal-invite card's actionLabel from "Send portal invite" to something that describes what the card itself does, not what the destination button does, for example "Show me" or "Take me there", since the card only opens the panel and highlights the real Send Portal Link button, it does not send anything on its own.

Do not change onDismiss, do not change honestLabel's default text, and do not change any other prop or the header bar.

VERIFY AFTER ACT:

grep -n "shadow-\[\|ring-concierge" /home/corby/jamm-os/frontend/src/components/concierge-inline/SuggestionCard.tsx

grep -n "actionLabel=" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Visit /dev/concierge-kit, confirm the SuggestionCard examples now show a genuinely visible soft glow around the card, in both light and dark mode, not just a thin faint line.

Visit Robert & Carol Tanner's client page, confirm the real portal-invite card shows the same visible glow, and confirm its button now reads the new label instead of Send portal invite.

Report pass or fail for both checks, describing what the glow actually looks like.

GIT:

git add -A

git commit -m "give SuggestionCard a real, visible soft glow using a box-shadow in the concierge color layered with the existing ring, replacing a ring that was too subtle to register as intentional per direct live feedback tonight, and change the portal-invite card's button label from Send portal invite to language describing what the card itself does, since the card only opens the panel and highlights the real Send Portal Link button rather than sending anything itself, removing the last piece of wording that duplicated the always-visible button below it"

git pull --rebase origin main

git push origin main