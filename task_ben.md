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

# Task: Render Concierge response progressively as SSE lines arrive, instead of only after the stream completes

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "while (true)" -A 25 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the read loop pushes each decoded line into allRawLines as it
arrives, but setMessages is only called once, after the loop's done branch
breaks out, with the fully assembled text.

## WHAT IS WRONG

Confirmed via live testing: even after fixing both backend generation paths
to emit progressively with no mid-sentence breaks, responses still appear
all at once in the UI. Root cause: the frontend's own read loop in
sendMessages only updates React state once, after the entire stream
finishes. Lines arrive from the network incrementally, but they are only
buffered into a local array (allRawLines) and never rendered until the
while loop's done condition is true and the loop breaks. No amount of
backend streaming correctness can produce a progressive UI feel if the
component that renders the text never updates mid-stream.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Inside the while (true) read loop in sendMessages, after each chunk of new
complete lines is extracted (the existing buffer.split('\n') / lines.pop()
logic), call setMessages to update the last message's content with the
text assembled so far, not just once at the end. Use the existing
assembleSSELines function on the lines accumulated so far on each iteration,
applying the same filterOutput and any other safe text transforms used at
the end, and update the in-progress message content incrementally:

        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            buffer += decoder.decode()
            if (buffer) allRawLines.push(buffer)
            break
          }
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          allRawLines.push(...lines)

          const partial = assembleSSELines(allRawLines)
            .replace(/\[TOPIC:\w+\]\s*$/, '')
            .trimEnd()
          if (partial) {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last && last.role === 'concierge') {
                updated[updated.length - 1] = { ...last, content: partial }
              }
              return updated
            })
          }
        }

Keep all the existing post-loop logic (filterOutput, parseDraftFromResponse,
handleConciergeAction, the final setMessages call with the draft attached,
the suggestion chips logic) exactly as is. The post-loop block still runs
once at the end and produces the final, fully correct message with its
draft parsed out, this change only adds incremental updates DURING the loop
so the user sees text appear progressively, with the final post-loop
setMessages call still being the authoritative final state.

Do not strip the ---DRAFT:--- block during the incremental updates if doing
so would require duplicating the full parseDraftFromResponse logic on every
partial chunk -- it is acceptable for the raw draft markers to be briefly
visible during streaming and then cleanly replaced by the final parsed
version once the stream completes, since this matches how the rest of the
app already treats streaming as progressively-rendered-then-finalized. Do
not change generate() or generate_with_tools() in the backend, this is a
frontend-only fix. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "setMessages" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: at least one new setMessages call now exists inside the while loop,
in addition to the existing post-loop call.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask a plain question with no draft involved, confirm text now visibly
   appears progressively as it streams, not all at once.
3. Ask for a draft requiring a tool call (e.g. follow-up email for a
   specific client), confirm the lead-in text and the draft both appear
   progressively rather than as one block, and the final rendered draft card
   still looks correct once streaming finishes.
4. Confirm no visual flicker or duplicate content appears as the in-progress
   text is replaced by the final parsed message.

Report what you observe at steps 2 and 3.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge chat now renders response text progressively as SSE lines arrive instead of only updating state once the entire stream completes, finally producing the visible progressive streaming effect the backend line-buffering fixes were intended to support"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.