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

# PRE-TASK
cd /home/corby/jamm-os
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

---

# POST-TASK — run after task completes
find /home/corby/jamm-os/app/api/concierge/ -name "*.py" | sort
ls /home/corby/jamm-os/migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort

---

TASK: Add firm_type to auth context and render intake message instantly

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before firm_type auth context task"
python3 -c "from app.api.concierge.route import router; print('OK')"

VERIFY BEFORE ACT:
grep -n "firm_type\|concierge_active" /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx
grep -n "AuthUser\|firms/me\|setUser" /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx
Paste output before touching anything.

---

Change 1: useAuth.tsx -- add firm_type and concierge_active to AuthUser interface

Find:
  totp_enabled?: boolean
}

Replace with:
  totp_enabled?: boolean
  firm_type?: string | null
  concierge_active?: boolean
}

The /firms/me endpoint already returns both fields. The fetch that populates setUser
already calls /firms/me. Confirm the fetch maps these fields onto the user object.

VERIFY AFTER ACT:
grep -n "firm_type\|concierge_active" /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx
Confirm both fields appear in the interface.

---

Change 2: ConciergePanel.tsx -- render intake message instantly when firm_type is null

The intake question is fixed content. It must not make an API call when firm_type is null.

VERIFY BEFORE ACT:
grep -n "hasInitialized\|__OPEN__\|sendMessages" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Paste output before touching anything.

Find the useEffect that fires __OPEN__:

OLD:
  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
      if (messages.length === 0) {
        sendMessages([{ role: 'user', content: '__OPEN__' }])
      }
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      api.post('/concierge/trigger-check').then(() => fetchNotifications()).catch(() => fetchNotifications())
    }
  }, [isOpen, sendMessages, fetchNotifications])

NEW:
  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
      if (messages.length === 0) {
        if (!user?.firm_type) {
          setMessages([{
            role: 'concierge',
            content: 'Welcome to JAMM Concierge. Before we start -- what does your firm do most? This lets me point you to the right setup path.\n\n1. Tax prep and returns\n2. Bookkeeping and monthly close\n3. Advisory and planning',
          }])
        } else {
          sendMessages([{ role: 'user', content: '__OPEN__' }])
        }
      }
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      api.post('/concierge/trigger-check').then(() => fetchNotifications()).catch(() => fetchNotifications())
    }
  }, [isOpen, sendMessages, fetchNotifications, user])

Do not change anything else in this file.

VERIFY AFTER ACT:
grep -n "firm_type\|intake\|Before we start" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Confirm the intake string appears once.

---

Post-task verification:
1. cd /home/corby/jamm-os/frontend
2. npm run build
   Zero TypeScript errors required before stopping.
3. find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort
4. find /home/corby/jamm-os/frontend/src/lib/hooks/ -name "*.tsx" | sort

Browser test:
- firm_type is null in the database for the test firm
- Open the panel
- Intake question must appear instantly with no Thinking... delay
- Select option 1 (Tax prep and returns)
- Confirm the model responds and sets firm_type
- Close and reopen the panel
- Confirm the tax_prep starters appear (API call this time, Thinking... is acceptable)