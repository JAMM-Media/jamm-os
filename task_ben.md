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

# Task: Fix morning briefing opening line still generating urgency language, and rename NEEDS ATTENTION to OPEN ITEMS in the detail prompt

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '1350,1353p' /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the current opening-line instruction reads: "One sentence max -- the single most important thing to know today, or 'All clear.' if nothing stands out."

grep -n "NEEDS ATTENTION" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm exactly which lines contain "NEEDS ATTENTION" in the detail prompt, so every occurrence is updated.

## WHAT IS WRONG

Confirmed via three-generation live test: MORNING_BRIEFING_PROMPT's opening line still produced "Four tax returns past their filing deadlines need immediate work" in 1 of 3 generations despite the expanded banned-word rule added in the previous task. The model treats the one-sentence opening as a headline context and instinctively reaches for urgency framing before the rules have anchored the response. A concrete example of what the opening line must and must not look like is more reliable than additional rule text, per observed behavior this session.

Separately, MORNING_BRIEFING_DETAIL_PROMPT still uses "NEEDS ATTENTION" as a section header in two places: the section content instruction and the rules block. This generates PDFs with "NEEDS ATTENTION" in all-caps bold, using the same phrase we renamed to "Open Items" in the conversational briefing prompt, creating an inconsistency between the two outputs that both represent the same JAMM PX feature.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

Fix 1 -- MORNING_BRIEFING_PROMPT opening line instruction:

Replace:

One sentence max -- the single most important thing to know today, or "All clear." if nothing stands out.

With:

One sentence max stating only a count and a status fact. No urgency framing, no directives, no advice.
Correct: "Four tax returns are past their filing deadline."
Correct: "Seven engagements have not been updated in over two weeks."
Correct: "All clear."
Never: "Four tax returns need immediate attention." (urgency framing -- banned)
Never: "You should follow up on four overdue returns." (directive -- banned)
Never: "Four returns are at risk." (risk framing -- banned)

Fix 2 -- MORNING_BRIEFING_DETAIL_PROMPT section header and rules:

Replace every occurrence of "NEEDS ATTENTION" with "OPEN ITEMS" in this prompt only. There are two occurrences:
1. The section header instruction line that begins "NEEDS ATTENTION"
2. The rules block line that reads "NEEDS ATTENTION, THIS WEEK, and RECENT ACTIVITY must always appear..."

Do not change any other text in either prompt. Do not change any other file.

## VERIFY AFTER ACT

grep -n "NEEDS ATTENTION" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: zero matches anywhere in the file.

grep -n "OPEN ITEMS\|Correct:\|Never:" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: all present -- two OPEN ITEMS occurrences in the detail prompt, and the Correct/Never examples in the opening-line instruction of the main briefing prompt.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. Clear briefing_sent_at for the test firm three times in sequence, triggering three separate fresh briefings:
   psql "postgresql://postgres:postgres@localhost:5432/jammpx_dev" -c "UPDATE firms SET briefing_sent_at = NULL WHERE id = '185314c9-e702-4eab-8600-249848022206';"
3. For each generation, read the opening line specifically. Confirm it states only a count and a status fact with no urgency framing, no directives, no banned words.
4. Download the detail briefing PDF from one of the three generations and confirm the section header now reads "OPEN ITEMS" instead of "NEEDS ATTENTION."
5. Confirm both the conversational briefing and the PDF use "Open Items" / "OPEN ITEMS" consistently, with no remaining "Needs Attention" anywhere.

Report the opening line text from all three generations, and the section header text from the downloaded PDF.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: morning briefing opening line now has concrete correct/wrong examples to prevent urgency framing, and NEEDS ATTENTION renamed to OPEN ITEMS in the detail prompt for consistency with the conversational briefing"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.