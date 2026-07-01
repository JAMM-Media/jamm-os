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

# Task 2: Add markdown formatting instruction to Concierge system prompt so responses use bold and structure where it helps

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '1,15p' /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the opening of PHASE_1_SYSTEM_PROMPT and the location of the first --- divider after the identity paragraph, where the new formatting instruction will be inserted.

grep -n "markdown\|bold\|\*\*\|formatting" /home/corby/jamm-os/app/api/concierge/prompts.py -i | grep -v "MORNING_BRIEFING\|DETAIL_PROMPT\|format_for_prompt\|_format_firm\|Critical formatting\|backtick\|CONCIERGE_ACTION"

Confirm zero existing formatting instructions in the main conversational prompt body.

## WHAT IS WRONG

Confirmed via live testing: the Concierge renders responses as plain prose with no markdown formatting even on complex multi-step how-to answers (e.g. portal color customization with 9 named slots, migration paths with multiple steps). The ReactMarkdown renderer in ConciergePanel.tsx is fully configured with custom components for bold (font-medium, proper dark mode color), headers (h2, h3), lists (ul, ol, li), and horizontal rules -- it is ready to render rich markdown. But the agent never generates markdown formatting because no instruction tells it to. This makes longer responses harder to scan than they need to be, with key UI terms like "Save branding" and "Set as active" buried in dense paragraphs at the same visual weight as surrounding text.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

Add a new RESPONSE FORMAT section immediately after the first --- divider in PHASE_1_SYSTEM_PROMPT (after the identity/scope paragraph, before the IDENTITY AND SCOPE heading or the SECURITY AND PRIVACY section, wherever the first --- divider currently sits). Insert:

---

RESPONSE FORMAT

The chat renderer supports markdown. Use it selectively to improve scannability -- not on every response, only where it genuinely helps.

Use **bold** for: specific UI element names the user needs to find or click (button labels, tab names, field names, section headings). Example: Navigate to **Settings** and select **Fee Schedule**.

Use numbered lists for: sequential steps where order matters (how-to instructions with 3 or more steps).

Use bullet lists for: parallel items with no meaningful order (lists of options, feature sets, status values).

Use plain prose for: short factual answers (1-3 sentences), yes/no questions, clarifying questions back to the user, and any response where adding structure would feel over-formatted relative to the question asked.

Never use headers (##, ###) in conversational responses. Headers are only used in the morning briefing format.

Never use horizontal rules (---) in conversational responses.

Keep responses concise. A complete answer to a specific question should rarely exceed 150 words. If a how-to answer needs more than 5 steps, consider whether the question can be broken into two separate answers.

Do not change any existing text in this file. Only insert the new block at the specified location.

## VERIFY AFTER ACT

grep -n "RESPONSE FORMAT\|Use \*\*bold\*\*\|plain prose" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: all three present in the main prompt body.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. Ask "how do I customize my client portal colors?" -- the same question that previously returned dense plain prose.
3. Confirm the response now uses bold for key UI terms (Portal, Portal Branding, Set as active, Save branding) and a numbered or bulleted list for the 9 color slots or the steps involved.
4. Ask "where are my clients?" -- confirm this short factual answer stays as clean plain prose with no over-formatting.
5. Ask "what are the session timeout options?" -- confirm this returns a clean list of the 6 options rather than a dense paragraph.

Report the exact response text for all three questions.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: add RESPONSE FORMAT section to Concierge system prompt instructing the agent to use bold for UI element names and lists for sequential steps, while keeping short factual answers as plain prose, matching the markdown renderer already configured in ConciergePanel.tsx"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.