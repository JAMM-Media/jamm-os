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

# Task: Switch Concierge model from claude-opus-4-8 to claude-sonnet-5, with controlled before/after quality verification

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '55,75p' /home/corby/jamm-os/app/api/concierge/cron.py

Confirm the TEMP comment and model="claude-opus-4-8" call at line 70.

sed -n '715,740p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm the TEMP comment and model="claude-opus-4-8" call at line 734.

## WHAT IS WRONG

Nothing is wrong -- this is a deliberate model upgrade test, not a bug fix. Claude Sonnet 5 was released today (June 30, 2026), with performance close to Opus 4.8 on most benchmarks and reportedly matching or slightly exceeding it on knowledge-work tasks specifically, at roughly 40-60% lower per-token cost during the introductory pricing period. The Concierge's workload (structured Q&A grounded in retrieved firm data, tool-calling for live data lookups, morning briefing generation) is closely aligned with the knowledge-work category where Sonnet 5 is reported to perform particularly well. Anthropic's own prompting guidance also notes Sonnet 5 interprets instructions more literally and explicitly than prior models, which is directly relevant given several bugs this session traced back to soft-instruction inconsistency (banned words occasionally slipping through, the CONCIERGE_ACTION marker not always firing).

This is currently a temporary swap already in place (claude-opus-4-8 substituting for claude-fable-5, which remains suspended under an export control directive with no announced return date). This task tests claude-sonnet-5 as a possible replacement for the temporary claude-opus-4-8 swap, not as a replacement for whatever the eventual long-term model choice will be once Fable 5 access is restored.

Confirmed via documentation: claude-sonnet-5 supports the output_config.effort parameter already in use (low/medium/high/xhigh/max), so the existing effort: "medium" setting on both calls will continue to work without modification.

## ACTION

File 1: /home/corby/jamm-os/app/api/concierge/cron.py

Change line 70 from:

            model="claude-opus-4-8",

To:

            model="claude-sonnet-5",

Update the TEMP comment above it:

        # TEMP: testing claude-sonnet-5 (released 2026-06-30) as a possible
        # replacement for the claude-opus-4-8 swap, itself a temporary
        # substitute for claude-fable-5 which remains suspended under an
        # export control directive with no announced return date. Sonnet 5
        # is reported to match or slightly exceed Opus 4.8 on knowledge-work
        # tasks at significantly lower cost, and to follow explicit
        # instructions more literally, which may improve reliability on
        # the banned-word and action-marker rules tuned for this prompt.
        # Revisit once Fable 5 access is restored.
        # https://www.anthropic.com/news/claude-sonnet-5

File 2: /home/corby/jamm-os/app/api/concierge/route.py

Change line 734 from:

                        model="claude-opus-4-8",

To:

                        model="claude-sonnet-5",

Update the TEMP comment above it the same way as in cron.py.

Do not change any of the claude-haiku-4-5-20251001 calls (route.py lines 329, 911, 942, 981) -- those are unrelated to this test. Do not change the effort: "medium" setting on either call. Do not touch any other file.

## VERIFY AFTER ACT

grep -rn "claude-sonnet-5\|claude-opus-4-8" /home/corby/jamm-os/app --include="*.py"

Expected: claude-sonnet-5 present at both former claude-opus-4-8 locations (cron.py and route.py), zero remaining claude-opus-4-8 references anywhere. claude-haiku-4-5-20251001 calls unchanged.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test -- this is the important part)

Restart the backend. Re-run every test this session has a documented baseline for, and compare quality against the known-good Opus results from earlier tonight:

1. Ask the Concierge how to invite a new staff member -- confirm it still correctly describes Partner/Staff/Manager roles.
2. Ask "where do I go to set my tax form prices?" then "what should I charge for a 1040?" -- confirm Fee Schedule navigation is correct and the pricing-judgment-call redirect still holds.
3. Ask "how do I customize my client portal colors?" -- confirm bold formatting on UI terms and a clean list for the 9 color slots, matching tonight's Opus baseline.
4. Ask "where are my clients?" -- confirm this stays as clean, appropriately brief plain prose, not over-formatted.
5. Trigger a fresh morning briefing (clear briefing_sent_at for the test firm first) three separate times, same as the earlier 3-generation banned-language test:
   psql "postgresql://postgres:postgres@localhost:5432/jammpx_dev" -c "UPDATE firms SET briefing_sent_at = NULL WHERE id = '185314c9-e702-4eab-8600-249848022206';"
   Confirm the opening line stays fact-only with no urgency language across all three generations, matching tonight's verified Opus baseline.
6. Ask "can I see the morning briefing again?" -- confirm the CONCIERGE_ACTION marker still reliably fires and the Download briefing button appears, matching tonight's fix.
7. Note the response speed subjectively for each of the above compared to how Opus felt tonight -- faster, the same, or slower.

Report the exact response text for tests 1-6, and your subjective speed impression for test 7. This is the evidence that determines whether Sonnet 5 is a genuine upgrade for this workload or whether it should be reverted back to claude-opus-4-8.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "test: swap Concierge model from claude-opus-4-8 to claude-sonnet-5 (released today) to evaluate quality and latency for this app's knowledge-work-heavy workload, updating TEMP comments to reflect this is testing a possible replacement for the temporary Opus swap"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.