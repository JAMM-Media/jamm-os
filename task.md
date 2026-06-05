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

TASK 1 OF 3: Output filtering -- ConciergePanel.tsx

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before output filtering"

VERIFY BEFORE ACT:
sed -n '245,265p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Paste output before touching anything.

---

Change 1: Add output filter in ConciergePanel.tsx before setMessages

Find exactly:
        const cleanContent = handleConciergeAction(assembled)

Replace with:
        const filteredAssembled = filterOutput(assembled)
        const cleanContent = handleConciergeAction(filteredAssembled)

Then add the filterOutput function immediately before the handleConciergeAction
function. Find exactly:

  function handleConciergeAction(raw: string): string {

Add this block immediately before it:

  function filterOutput(text: string): string {
    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g
    const EIN_PATTERN = /\b\d{2}-\d{7}\b/g
    const LEAK_PHRASES = [
      'my instructions are',
      'my system prompt',
      'i was instructed to',
      'i am instructed to',
      'the system prompt says',
      'my prompt says',
      'i have been told to',
      'i have been configured',
      'as per my instructions',
      'according to my instructions',
    ]

    if (SSN_PATTERN.test(text) || EIN_PATTERN.test(text)) {
      console.error('[SECURITY] PII pattern detected in model output -- redacting')
      text = text.replace(SSN_PATTERN, '[REDACTED]')
      text = text.replace(EIN_PATTERN, '[REDACTED]')
    }

    const lower = text.toLowerCase()
    for (const phrase of LEAK_PHRASES) {
      if (lower.includes(phrase)) {
        console.error(`[SECURITY] System prompt leak phrase detected in output: ${phrase}`)
        return 'I am JAMM Concierge. I am here to help you use JAMM PX.'
      }
    }

    return text
  }

Do not change anything else.

VERIFY AFTER ACT:
grep -n "filterOutput\|SSN_PATTERN\|EIN_PATTERN\|LEAK_PHRASES\|REDACTED\|filteredAssembled" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Confirm all terms appear.

Post-task:
cd /home/corby/jamm-os/frontend
npm run build
Zero TypeScript errors required before stopping.