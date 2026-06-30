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

# Task: Strengthen morning briefing prompt to reliably prevent urgency/advice language leaking into output

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "MORNING_BRIEFING_PROMPT" -A 40 /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the current prompt text exactly as it stands, including the existing "Never use: urgent, immediate, critical, must, should, action required, needs attention" line and the "### \u26a0\ufe0f Needs Attention" section header.

## WHAT IS WRONG

Confirmed via live testing: a real morning briefing rendered the line "Four tax returns past their April 15 deadline need immediate client follow-up." The word "immediate" appears explicitly on this prompt's own banned-word list, yet it rendered anyway. This is the same class of soft-instruction inconsistency seen elsewhere in this session (the morning briefing re-request stutter), where a single inline rule is followed most of the time but not reliably enough for content with real legal/compliance sensitivity, per the Phase 5A spec's explicit prohibition on urgency framing and action directives in this specific feature.

Separately, the section header itself is literally "Needs Attention," which is the same phrase the rule tells the model never to use. This is not a contradiction in effect, since a section label and prose text are different things, but it likely makes the banned phrase feel "already in use" to the model, weakening adherence to avoiding it elsewhere in the same response.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

In MORNING_BRIEFING_PROMPT, strengthen the banned-language rule from a single inline list into an explicit, absolute instruction with a stated consequence, matching the pattern already proven effective elsewhere in this file for soft-instruction reliability problems:

Replace:

- Never use: urgent, immediate, critical, must, should, action required, needs attention

With:

- Absolutely never use these words or any close variant, anywhere in the response, including inside bullet text: urgent, immediate, critical, must, should, action required, needs attention, important, priority, asap, right away, as soon as possible. Before finalizing your response, check every sentence against this list. If any of these words appear, rewrite that sentence to state only the fact, with no urgency framing. This is a firm legal requirement, not a style preference -- the briefing reports facts only, it never tells the firm owner what to prioritize or how quickly to act.

Also rename the section header from "Needs Attention" to a more neutral, purely descriptive label that does not itself sound like a directive, to reduce the chance the model treats the banned phrase as already acceptable in context:

Replace:

### \u26a0\ufe0f Needs Attention

With:

### \u26a0\ufe0f Open Items

Update the corresponding reference to "Needs Attention" later in the rules block (the line "Needs Attention must only list items..." and "Never include in Needs Attention...") to say "Open Items" instead, keeping the underlying logic of those rules completely unchanged, only the label.

Do not change MORNING_BRIEFING_DETAIL_PROMPT or any other prompt in this file. Do not change the overall format, the This Week or Recent Activity sections, or the client_count/engagement_count footer line.

## VERIFY AFTER ACT

grep -n "Open Items\|Absolutely never use these words" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: both present, and "Needs Attention" no longer appears anywhere in MORNING_BRIEFING_PROMPT.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. Clear the briefing_sent_at cooldown for the test firm in the database so a fresh briefing generates: 
   psql "postgresql://postgres:postgres@localhost:5432/jammpx_dev" -c "UPDATE firms SET briefing_sent_at = NULL WHERE id = '185314c9-e702-4eab-8600-249848022206';"
3. Open a fresh dashboard session and trigger a real morning briefing.
4. Read the full output carefully and confirm none of the banned words or close variants appear anywhere, including inside bullet text.
5. Repeat steps 2-4 two more times (clearing the cooldown each time) to confirm this holds consistently across multiple generations, not just once, since the original bug was intermittent rather than constant.

Report the full text of all three briefing generations.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: strengthen morning briefing prompt's urgency-language ban from a simple word list to an absolute, explicitly-enforced rule, and rename the Needs Attention section header to Open Items to remove the banned phrase from the prompt's own structure"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.