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

# Task: Fix client page tab not switching on same-route query param navigation

USE: claude sonnet

## VERIFY BEFORE ACT

```bash
sed -n '54,60p' /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx
```

Confirm activeTab is initialized via a lazy useState function that reads
searchParams.get('tab') ONLY on first mount.

```bash
grep -n "router.push(\`/clients/\${targetClientId}?tab=messages\`)" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
```

Confirm both Concierge Send buttons (chat draft and notification draft) call
this same router.push pattern.

---

## WHAT IS WRONG

Confirmed via live testing: clicking "Open to send" in the Concierge panel
correctly shows the confirm dialog, correctly calls router.push to add
?tab=messages to the URL, and the browser URL bar correctly updates -- but
the Messages tab never visually activates. The user remains on whatever tab
was already active (Overview).

Root cause: activeTab is a useState with a lazy initializer function that
reads the URL's tab param only once, on the component's first mount. When
the user is already on this exact client's page and router.push only
changes the query string on the same route, Next.js does not remount the
page component, it just updates the URL. Since the component never
remounts, the lazy useState initializer never re-runs, and activeTab never
updates to reflect the new ?tab=messages value.

This is a pre-existing gap in the page's own tab-sync logic, not something
introduced by the Concierge fix. It would affect any same-page navigation
that tries to switch tabs via the URL while already on that page. The
Concierge fix simply was the first thing to expose it.

---

## ACTION

File: `/home/corby/jamm-os/frontend/src/app/clients/[id]/page.tsx`

Find the activeTab declaration:

```typescript
  const [activeTab, setActiveTab] = useState(() => {
    const p = searchParams.get('tab')
    return p && CLIENT_TABS.some((t) => t.key === p) ? p : 'overview'
  })
```

Directly below it, add a useEffect that watches searchParams and updates
activeTab whenever the URL's tab param changes, even if the component is
already mounted:

```typescript
  useEffect(() => {
    const p = searchParams.get('tab')
    if (p && CLIENT_TABS.some((t) => t.key === p) && p !== activeTab) {
      setActiveTab(p)
    }
  }, [searchParams])
```

This keeps the lazy initializer for correct first-load behavior, so a direct
link with ?tab=messages still opens straight to that tab on first visit,
while also reacting to query param changes that happen after the component
has already mounted, which is exactly the case the Concierge Send button
hits.

Do not touch the lazy initializer. Do not touch any other tab logic, the tab
UI, props, or styling. Do not touch any other file.

---

## VERIFY AFTER ACT

```bash
grep -n "searchParams.get('tab')" /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx
```

Expected: 2 occurrences now, the original lazy initializer and the new
useEffect.

```bash
cd /home/corby/jamm-os/frontend
npm run build
```

Expected: zero TypeScript errors.

---

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. While already on a specific client's page (e.g. Overview tab active),
   trigger a Concierge CLIENT_EMAIL draft and click "Open to send."
3. Click OK on the confirm dialog.
4. Confirm the Messages tab now visually activates, the tab underline moves
   to Messages, the URL shows ?tab=messages, and the message compose box is
   visible and pre-filled with the draft text.
5. Regression check: manually click between other tabs (Overview,
   Engagements, Documents) to confirm normal tab-clicking still works
   exactly as before. This fix must not interfere with manual tab clicks
   that don't go through the URL.
6. Regression check: open a fresh browser tab directly to a URL like
   /clients/{id}?tab=messages, typed directly, simulating a bookmark or
   shared link, and confirm it still opens straight to the Messages tab on
   first load. This confirms the original lazy initializer behavior is
   unchanged.

Report what you observe at step 4 specifically.

---

## GIT

```bash
cd /home/corby/jamm-os
git add "frontend/src/app/clients/[id]/page.tsx"
git commit -m "fix: client page tab now syncs with URL query param changes after mount, not just on first load -- fixes Concierge Open to send not switching to Messages tab"
git pull --rebase origin main
git push origin main
```

If conflicts on task.md use --theirs. Conflicts on source files use --ours.