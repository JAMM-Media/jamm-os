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

# Task: Convert NotesPanel's uncached /users/ fetch to React Query for proper caching and deduplication

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '130,145p' /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx

Confirm the current implementation: a plain useEffect calling api.get('/users/') with no caching, no deduplication, and no protection against re-firing if the component re-renders or remounts.

grep -n "import.*useQuery" /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx

Confirm whether useQuery is already imported in this file (it likely is not, since the current implementation uses plain useEffect).

## WHAT IS WRONG

Confirmed via live testing and code tracing: NotesPanel fetches the full staff list via a raw useEffect + api.get('/users/') call with no caching layer, unlike other data-fetching in this codebase that correctly uses React Query's useQuery (e.g. Sidebar.tsx's notifData, firmData, and myIntegrations, and the client detail page's own qboAr). This staff list rarely changes within a session, making it a good candidate for React Query's built-in caching, which would prevent redundant refetches if NotesPanel re-renders or remounts, and would deduplicate simultaneous requests if multiple instances of this component happen to render at once.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx

Add useQuery to the existing react-query import (or add the import if not present).

Replace the existing useEffect + api.get('/users/') pattern with a useQuery call using a stable query key and a reasonable staleTime, matching the pattern already used elsewhere in this codebase (e.g. Sidebar.tsx's firmData query):

  const { data: staffData } = useQuery({
    queryKey: ['users-list'],
    queryFn: () => api.get('/users/').then((res) => res.data),
    staleTime: 5 * 60 * 1000,
  })

Adjust the exact shape of how staffData is then used (setting local state, mapping to a dropdown list, etc.) to match whatever the removed useEffect was doing with the fetched data -- preserve the existing behavior and UI exactly, only change how the data is fetched and cached, not what is done with it once available.

Do not change any other fetch in this file. Do not change NotesPanel's other useEffect (the one at line 159, unrelated to this fix). Do not touch any other file.

## VERIFY AFTER ACT

grep -n "useQuery.*users-list\|queryKey: \['users-list'\]" /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx

Expected: present.

grep -n "useEffect.*api.get('/users/')" /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx

Expected: no longer present -- the raw useEffect fetch is fully replaced.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend with a clean build.
2. Open DevTools Network tab, open a client detail page, and specifically look at how many times a request to /users/ fires.
3. Confirm the staff/user dropdown functionality inside Notes still works exactly as before (assigning, mentioning, or whatever it was used for).
4. Navigate away and back to the same or a different client's Notes section, confirm the /users/ request does not refire within the 5-minute staleTime window (React Query should serve from cache).

Report what you observe at steps 2 and 4.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "perf: NotesPanel now fetches the staff/users list via React Query instead of a raw uncached useEffect, adding proper caching and deduplication to prevent redundant refetches on re-render or remount"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.