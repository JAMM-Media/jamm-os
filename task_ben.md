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

# Task: Fix client Messages compose box stuck at one line, cannot preview multi-line drafts

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "function handleInput" -A 6 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the existing auto-grow pattern used by the Concierge panel's own input box, which correctly grows with content up to a max height.

sed -n '976,988p' /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx

Confirm the Messages tab compose textarea currently has rows={1}, no onInput
handler, and resize-none, with only a static minHeight/maxHeight in its style
prop and nothing that actually grows it as the user types.

## WHAT IS WRONG

Confirmed via live testing: when a Concierge draft is pre-filled into the
Messages tab compose box, the user can only see one line of the message at
a time. There is no way to preview a multi-line message before sending it,
since the textarea never grows past its initial single row, and manual
resize is disabled. This affects every message in this box, not just
Concierge-prefilled ones, but it is most visible there since drafts are
typically several sentences long.

Root cause: the textarea has rows={1} and resize-none, with a maxHeight set
in its style only as a ceiling, but nothing actually grows its height as
content is typed or pre-filled in. The Concierge panel's own chat input box
a few files over already solves this exact problem correctly with an
onInput handler that sets the textarea's height to its scrollHeight, capped
at a max. This compose box never got the same handler.

## ACTION

File: /home/corby/jamm-os/frontend/src/app/clients/[id]/page.tsx

Add an onInput handler to the Messages compose textarea matching the
existing working pattern from ConciergePanel.tsx's handleInput function:

onInput={(e) => {
  const el = e.currentTarget
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}}

Add this alongside the existing onChange and onKeyDown props on the same
textarea. Keep rows={1} as the initial collapsed state, that part is
correct, it should start small and grow only when there is content.

Also add a useEffect that runs this same height calculation whenever
messageCompose changes via something other than direct typing, specifically
when it gets set by the prefill-message live action or the sessionStorage
prefillMessage path, since onInput only fires on user keystrokes, not on a
value being set programmatically. A ref on the textarea will be needed for
this; add one if one does not already exist for this element, and use it in
a useEffect keyed on messageCompose:

useEffect(() => {
  if (messageComposeRef.current) {
    messageComposeRef.current.style.height = 'auto'
    messageComposeRef.current.style.height = Math.min(messageComposeRef.current.scrollHeight, 120) + 'px'
  }
}, [messageCompose])

Do not change resize-none, the placeholder text, the send button, or any
other logic in this section. Do not touch ConciergePanel.tsx or any other
file.

## VERIFY AFTER ACT

grep -n "onInput\|messageComposeRef" /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx

Expected: both present on or near the compose textarea.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Trigger a multi-sentence Concierge draft for a specific client and click
   Open to send.
3. Confirm the compose box on the Messages tab now visibly grows to show
   multiple lines of the pre-filled draft, not just one line with the rest
   hidden.
4. Manually type a long multi-line message directly into the box (not via
   Concierge) and confirm it also grows correctly as you type.
5. Confirm the box stops growing at a reasonable max height and switches to
   internal scrolling for very long messages, rather than growing
   indefinitely.

Report what you observe at step 3 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: client Messages compose box now auto-grows to show multi-line content instead of staying stuck at one visible line, matching the existing working pattern in ConciergePanel's own chat input"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.