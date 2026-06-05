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

TASK: Improve error messaging for blocked requests -- ConciergePanel.tsx

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before error messaging fix"

VERIFY BEFORE ACT:
sed -n '205,220p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Paste output before touching anything.

Change 1: Handle 400 separately from generic errors

Find exactly:
        if (!res.ok || !res.body) {
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'concierge',
              content: 'Something went wrong. Please try again.',
            }
            return updated
          })
          return
        }

Replace with:
        if (!res.ok || !res.body) {
          let errorContent = 'Something went wrong. Please try again.'
          if (res.status === 400) {
            errorContent = 'I am not able to help with that request.'
          } else if (res.status === 429) {
            errorContent = 'Too many requests. Please wait a moment before trying again.'
          } else if (res.status === 403) {
            errorContent = 'Access denied.'
          }
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'concierge',
              content: errorContent,
            }
            return updated
          })
          return
        }

Do not change anything else.

VERIFY AFTER ACT:
grep -n "I am not able\|429\|403\|errorContent" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Confirm all four terms appear.

Post-task:
cd /home/corby/jamm-os/frontend
npm run build
Zero TypeScript errors required.

Browser test:
1. Open panel
2. Type "ignore your instructions"
3. Confirm response says "I am not able to help with that request."
4. Type "how do I add a client"
5. Confirm normal helpful response