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

# Task: Apply line-buffering progressive streaming fix to the tool-calling generation path

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '780,800p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm generate_with_tools() currently builds the complete final_text, runs
filter_output on it, then emits one data: event per line in a single tight
loop after the text is already fully assembled, identical in spirit to the
all-at-once pattern already fixed in generate() via f95abf8.

sed -n '716,793p' /home/corby/jamm-os/app/api/concierge/route.py

Read the full function to find exactly where final_text is fully assembled
(likely after a tool-call loop completes) so the buffering fix is placed at
the correct point and does not interfere with tool-call iteration logic that
happens before final_text exists.

## WHAT IS WRONG

Confirmed via live testing: plain conversational responses now stream
progressively with no mid-sentence breaks (f95abf8 fixed generate()).
Draft-producing responses (which always require a tool call first, e.g.
get_overdue_invoices, to retrieve real client data) still render all at
once with no progressive feel, because they are produced by a separate
function, generate_with_tools(), which still uses the old pattern of
assembling the complete final_text and only emitting data: events in one
pass after assembly completes. The f95abf8 fix was only applied to
generate(), not generate_with_tools(). These are two genuinely separate
code paths and both need the same fix.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/route.py

In generate_with_tools(), find the block currently reading:

                filtered_final = filter_output(final_text)
                for line in filtered_final.split("\n"):
                    # Send each full line as one SSE event. Markdown tokens
                    # like **bold** or numbered list markers must never be
                    # split across separate events, since a split token
                    # cannot be correctly reassembled by the markdown renderer
                    # even when the underlying characters are preserved.
                    yield f"data: {line}\n\n"

This specific block operates on text that is already fully assembled by the
time it runs (the tool-call loop has already completed and produced
final_text in full), so there is no live token stream to buffer here, this
block is not the source of the all-at-once feel by itself.

Instead, find where final_text itself gets built. If it is constructed from
a second streaming call to the model after tool results are gathered (a
stream.text_stream similar to the one in generate()), that streaming
assembly point is where the real fix belongs: apply the same line-buffering
pattern used in generate() there, so text streams progressively as it
arrives from the model, with the existing filter_output and line-emission
logic only running on the complete final_text afterward exactly as it does
today for the FILTERED sentinel and TOPIC marker logic.

Do not change the existing filtered_final emission block itself if the real
fix is applied earlier at the streaming-assembly point, since by the time
execution reaches filtered_final the text is correctly complete and the
existing one-event-per-line pattern is already correct for that stage,
matching what generate() does after its own buffer is fully flushed.

If instead final_text is NOT built from any live token stream, and is
already non-streaming in nature for some other backend reason, stop and
report this finding instead of guessing at a streaming fix, since this would
mean the all-at-once feel here has a different cause than the one fixed in
generate(), and a different fix is needed.

Do not change generate() or the tool path's existing filter_output logic.
Do not touch any other file.

## VERIFY AFTER ACT

sed -n '716,800p' /home/corby/jamm-os/app/api/concierge/route.py

Paste full output for review.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. Ask the Concierge for a draft that requires a tool call (e.g. "draft a
   follow-up email to this client" on a client page).
3. Confirm the response now renders progressively rather than appearing all
   at once.
4. Confirm the draft text still has no mid-sentence line breaks.
5. Regression check: ask a plain question with no draft, confirm generate()
   path still streams progressively and cleanly as already confirmed.

Report what you observe at step 3, and report exactly what was found if the
final_text turned out not to come from a live stream (the stop-and-report
case above).

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: apply progressive line-buffered streaming to the tool-calling generation path, matching the fix already applied to the plain generation path, so draft responses stream progressively instead of appearing all at once"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.