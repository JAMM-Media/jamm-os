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

TASK: Give the portal-link highlight a real, visible glow instead of a subtle small ring, so it's catchable across the width of the screen

USE: claude sonnet

VERIFY BEFORE ACT:

grep -n "portalLinkHighlight ?" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

grep -n "color-brand-btn" /home/corby/jamm-os/frontend/src/app/globals.css

Confirm the current highlight is ring-2 ring-brand-btn/40 with animate-pulse, no glow/shadow, and confirm the real hex value of brand-btn before hardcoding an rgba value.

WHAT THIS IS:

Direct, live feedback tonight: the Concierge suggestion card sits on the left side of the client detail page, while the button it's meant to draw attention to, Send Portal Link, sits on the right side of the same page. The current highlight, a small ring at 40 percent opacity, is not visually loud enough to catch attention across that distance, especially in peripheral vision, since the person's eyes are on the card when they click "Show me," not on the button. Earlier tonight the exact same underlying problem, a highlight too subtle to register, was fixed for SuggestionCard by adding a real box-shadow glow layered with its ring. This task applies that same proven pattern to the portal-link button's highlight, using the button's own existing brand-btn blue rather than inventing a new color.

CHANGE INSTRUCTIONS:

Add a box-shadow glow in the brand-btn color at moderate opacity, layered with the existing ring-2 ring-brand-btn/40 and animate-pulse, sized generously enough to be clearly visible without needing to look directly at the button, for example a shadow-[0_0_20px_rgba(58,106,148,0.45)] or equivalent tuned value. Keep animate-pulse as-is, the combination of the existing pulse animation and the new glow should make the highlight genuinely catch the eye across the width of the screen. Do not change the highlight's 7 second duration, the scrollIntoView behavior, or anything else about when or how the highlight is triggered, this is purely a stronger visual treatment for the highlighted state itself.

VERIFY AFTER ACT:

grep -n "shadow-\[\|ring-brand-btn" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

On Robert & Carol Tanner's page, click "Show me" on the portal-invite card. Confirm the Send Portal Link button now shows a genuinely noticeable glow, catchable without staring directly at it, lasting the same 7 seconds as before.

Report pass or fail, describing whether it's actually catchable in peripheral vision now.

GIT:

git add -A

git commit -m "add a real box-shadow glow to the portal-link highlight, using the button's existing brand-btn blue, reusing the same glow pattern that fixed SuggestionCard's visibility problem earlier tonight, since direct feedback confirmed the previous small ring at 40 percent opacity was not catchable across the horizontal distance between the suggestion card on the left and the Send Portal Link button on the right of the same page"

git pull --rebase origin main

git push origin main