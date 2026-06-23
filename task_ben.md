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

# Task: Restore progressive streaming while keeping the mid-sentence-break fix, via line buffering

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '621,632p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm the current streaming path (from commit c46ba79) accumulates the
full text in 'assembled' and only emits data: events after the stream loop
completes, one per real line. This produces clean output but kills
progressive streaming.

## WHAT IS WRONG

The previous fix (c46ba79) correctly eliminated mid-sentence line breaks but
did so by waiting for the entire response before emitting anything, removing
the progressive token-by-token streaming effect. With response latency
already a concern, a multi-second blank wait followed by a sudden full
response is a worse experience than progressive rendering.

The goal is both properties at once: stream progressively AND never split a
line mid-sentence. The way to get both is to buffer incoming token fragments
and flush only complete lines as they finish, keeping any partial trailing
line in the buffer until its newline arrives. A data: event then always
represents a complete real line, which is what the frontend assembleSSELines
correctly assumes, while lines still appear progressively as they complete
rather than all at once at the end.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/route.py

Replace the current accumulate-then-emit streaming block:

            assembled = ""
            for text in stream.text_stream:
                assembled += text
            for line in assembled.split("\n"):
                yield f"data: {line}\n\n"

with a line-buffering version that emits complete lines progressively:

            assembled = ""
            buffer = ""
            for text in stream.text_stream:
                assembled += text
                buffer += text
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    yield f"data: {line}\n\n"
            if buffer:
                yield f"data: {buffer}\n\n"

This streams each complete line the moment its newline arrives, while any
in-progress partial line stays in the buffer until finished, so no line is
ever emitted mid-sentence. assembled is still maintained in full for the
filter_output and [TOPIC:] logic that follows, which is unchanged.

Leave the filter_output block, the [FILTERED] sentinel logic, and the
[TOPIC:...] trailing marker exactly as they are. Do not change the tool
path. Do not change the frontend assembleSSELines. Do not touch any other
file.

## VERIFY AFTER ACT

sed -n '621,635p' /home/corby/jamm-os/app/api/concierge/route.py

Expected: the line-buffering while-loop is present, assembled still
accumulates the full text, and a final flush of any remaining buffer exists.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. With DevTools Console open, ask the Concierge to draft a follow-up email
   for a specific client.
3. Confirm visually that the response now streams progressively again,
   appearing line by line rather than all at once after a blank wait.
4. Find the [CONCIERGE RAW] log line and confirm there are still NO
   mid-sentence line breaks. Sentences whole, breaks only at real paragraph
   boundaries.
5. Regression check: ask a question returning a numbered list and bold text,
   confirm both still render correctly and nothing splits mid-token while
   streaming progressively.

Report both whether streaming is progressive again (step 3) and what the
[CONCIERGE RAW] log shows (step 4).

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "perf: restore progressive Concierge streaming by buffering token fragments and flushing only complete lines, keeping the mid-sentence-break fix while bringing back line-by-line rendering instead of a single all-at-once response"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.