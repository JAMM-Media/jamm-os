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

TASK 3: Gate suggestion chips on the reveal animation finishing, not on response completion

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "revealedWordCount" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "suggestions.length > 0 && i === messages.length - 1" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm both matches exist before proceeding. This task touches the same streaming and reveal logic that caused real problems earlier this session, so read the full surrounding function before editing rather than editing blind off the grep line alone.

CHANGE INSTRUCTIONS:
In the render condition that currently shows suggestion chips (the block starting with the condition checking autopilotOn, suggestions.length, i === messages.length minus one, and msg.role), add an additional condition requiring the reveal animation for that message to have finished. Specifically, the chip block should only render once revealedWordCount is greater than or equal to the total word count of msg.content (msg.content.split(/\s+/).filter(Boolean).length), so the chip never appears fully formed while the message text above it is still animating in.

Do not change the reveal animation timing or speed itself, only the condition gating when suggestions become visible.

VERIFY AFTER ACT:
grep -n "revealedWordCount >= \|revealedWordCount >=" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the new condition appears directly inside the same conditional block as suggestions.length > 0, not as a separate unrelated check.

MANUAL VERIFICATION:
Full kill and restart of both servers, and a full .next wipe, since this touches streaming and reveal state. Ask a question that returns a longer response with a topic chip. Watch carefully whether the chip appears only after the full response has finished animating in, not while it is still revealing word by word.

GIT:
git add -A
git commit -m "gate suggestion chips on reveal animation completion"