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

# Task: Bypass the LLM entirely for the deterministic __OPEN__ trigger, eliminating risk of any model overriding the fixed-output instruction

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '290,340p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm the concierge_chat function signature: current_firm (with firm_type and concierge_active available), current_user, db all present as parameters before any model call happens. Confirm the guard classifier already special-cases last_user_msg == "__OPEN__" by skipping the safety classifier for it, establishing __OPEN__ as an already-recognized sentinel in this function.

grep -n "def generate_and_log" -A 15 /home/corby/jamm-os/app/api/concierge/route.py

Confirm what generate_and_log logs via ConciergeQuestionLog, to decide whether the __OPEN__ bypass should also create a log entry or deliberately skip it since __OPEN__ is not a real user question (the guard classifier already treats it this way).

## WHAT IS WRONG

Confirmed via live testing on a clean build: the model (currently claude-sonnet-5, previously claude-opus-4-8 during earlier testing) is sometimes asked to reproduce an exact fixed string for the __OPEN__ empty-state trigger ("Let's get ready to work. I'm ready to help with anything you need." when firm_type is set, or the three-option onboarding question when firm_type is null). The prompt explicitly instructs "output exactly this and nothing else" and "do not add any other text," but this is inherently unreliable to enforce via prompt instruction alone, since the model has full tool access and real firm data available at generation time, creating constant pressure to be "more helpful" than the fixed string allows. This was confirmed to fail with claude-sonnet-5 in production testing, generating rich free-form status reports with invented headers and proactive advice instead of the required string.

The __OPEN__ output is fully deterministic given only current_firm.firm_type -- there are exactly four possible correct outputs (the onboarding question if firm_type is null, or one of three identical "Let's get ready to work" messages if firm_type is tax_prep, bookkeeping, or advisory -- note the three firm_type variants currently produce identical text per prior session work, so there are really only two distinct possible outputs). Since there is no actual ambiguity or judgment involved, the correct fix is to stop asking any LLM to generate this output at all, and instead return the fixed string directly from the backend. This makes the __OPEN__ trigger 100% reliable regardless of which model powers the rest of the Concierge, faster (no generation wait), and cheaper (no API call), while leaving every other Concierge interaction (which genuinely benefits from model-generated, context-aware responses) completely unaffected.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/route.py

In concierge_chat, immediately after current_firm and body are available (near the top of the function, before the guard classifier block, api_key checks, or any model-related setup), add a bypass for the __OPEN__ sentinel:

    last_user_msg_for_open_check = next(
        (m.content for m in reversed(body.messages) if m.role == "user"),
        None,
    )
    if last_user_msg_for_open_check == "__OPEN__" and len(body.messages) == 1:
        if not current_firm.firm_type:
            open_text = (
                "Welcome to JAMM Concierge. Before we start -- what does your firm do most? "
                "This lets me point you to the right setup path.\n"
                "1. Tax prep and returns\n"
                "2. Bookkeeping and monthly close\n"
                "3. Advisory and planning"
            )
        else:
            open_text = "Let's get ready to work. I'm ready to help with anything you need."

        def generate_open_bypass():
            for line in open_text.split("\n"):
                yield f"data: {line}\n\n"

        return StreamingResponse(generate_open_bypass(), media_type="text/event-stream")

The len(body.messages) == 1 check ensures this only fires on the very first __OPEN__ trigger of a session (a single-message array containing only the __OPEN__ sentinel), not on any later message that might coincidentally match, matching how the frontend only ever sends __OPEN__ as the sole message in a fresh array.

Do not add a ConciergeQuestionLog entry for this bypass path, since __OPEN__ is not a real user question and the guard classifier already treats it as a non-question sentinel elsewhere in this same function. Add a one-line comment above the bypass explaining this is intentional.

This bypass makes the entire EMPTY STATE -- FIRST OPEN section of prompts.py (the exact-output instructions, the three intake_example blocks, the three firm_type-specific instruction blocks) dead code that is never actually reached by a real __OPEN__ trigger anymore, since the backend now short-circuits before ever calling the model for this case. Do not delete that section of prompts.py in this task -- leave it in place as a reference/fallback in case the bypass is ever removed, but note in your verification output that it is no longer live.

Do not change the morning briefing endpoint, the dashboard-specific opening flow in the frontend, or any other part of this file. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "generate_open_bypass\|last_user_msg_for_open_check" /home/corby/jamm-os/app/api/concierge/route.py

Expected: both present, positioned before the guard classifier block.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. Clear sessionStorage (or use a private window), navigate to a non-dashboard page (Engagements or Clients) for a firm with firm_type already set, and open the Concierge panel for the first time in this session.
3. Confirm the message is exactly "Let's get ready to work. I'm ready to help with anything you need." with nothing else -- no free-form content, no firm data, no extra sections -- regardless of which model is currently configured as the primary model.
4. Check DevTools Network tab for this specific request and confirm no call to api.anthropic.com appears for it (bypass should be instant, no LLM round trip).
5. Regression check: ask a real follow-up question in the same session (not __OPEN__) and confirm normal model-generated responses still work correctly.
6. Regression check: test the dashboard morning briefing flow separately and confirm it is completely unaffected by this change.

Report what you observe at steps 3 and 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: bypass the LLM entirely for the deterministic __OPEN__ empty-state trigger, returning the fixed opening message directly from the backend instead of asking the model to reproduce it exactly, eliminating the risk of any model overriding this hard constraint regardless of which model is configured as primary"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.