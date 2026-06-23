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

# Task: Fix hydration mismatch from messages state lazy-reading sessionStorage on initial render

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "const \[messages, setMessages\] = useState" -A 10 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current lazy initializer checks typeof window !== 'undefined' and
reads sessionStorage directly inside useState, exactly as described below.

grep -n "hasMounted" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the existing hasMounted pattern already used elsewhere in this file
for the same class of problem (panel open/close animation), so the new fix
follows the same established pattern rather than inventing a new one.

## WHAT IS WRONG

Confirmed via live testing: a hydration mismatch error fires when the
Concierge panel renders with prior chat history in sessionStorage. React's
own error output names the exact cause: a server/client branch using
typeof window !== 'undefined' inside a useState lazy initializer.

Root cause: messages is initialized via a lazy useState function that
checks typeof window !== 'undefined' and reads sessionStorage directly. On
the server, window does not exist, so this always evaluates to the empty
array, and the server renders the empty starter-prompts state. On the
client, window exists and sessionStorage already has saved messages from
earlier in the session, so the client renders actual chat history instead.
Server and client disagree on what the initial render should look like for
the same component, which is the textbook cause of this exact React error.

This is the same underlying disease as the original panel-open hydration fix
from this codebase's history, just in a different piece of state that never
received the same fix.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Change the messages initializer to always start as an empty array on both
server and client, with no window check:

const [messages, setMessages] = useState<Message[]>([])

Then add a useEffect that runs once after mount to hydrate from
sessionStorage, matching the existing hasMounted-guarded pattern already
used in this file for other post-mount-only logic:

useEffect(() => {
  try {
    const stored = sessionStorage.getItem('jamm_concierge_messages')
    if (stored) setMessages(JSON.parse(stored) as Message[])
  } catch {
    // ignore parse errors
  }
}, [])

Place this useEffect near the existing useEffect that already writes
messages to sessionStorage (the one with the matching
sessionStorage.setItem('jamm_concierge_messages', ...) call), so the read
and write logic for this key live close together. Do not change that
existing write-effect. Do not change the hasMounted state or its existing
uses elsewhere in the file. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "useState<Message\[\]>(\[\])" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present, confirming the lazy initializer with the window check is
gone.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open the Concierge panel and send a few messages so sessionStorage has
   chat history saved.
3. Navigate to a different page within the app (a same-session client-side
   navigation, not a hard reload) and reopen the panel.
4. Confirm no hydration error appears in the console, and the prior chat
   history still correctly appears once the client mounts and the
   useEffect runs.
5. Regression check: with no prior chat history (fresh sessionStorage),
   confirm the empty starter-prompts state still renders correctly with no
   flash of mismatched content.

Report what you observe at step 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge messages state no longer reads sessionStorage inside a useState lazy initializer, eliminating a server/client hydration mismatch; history is now restored in a post-mount useEffect instead"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.