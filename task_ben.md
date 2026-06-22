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

# Task: Fix SOURCE line fragment leaking into draft email body on multi-line wrap

USE: claude sonnet

## VERIFY BEFORE ACT

```bash
grep -n "sourceMatch\|SOURCE:" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
```

Confirm the current regex is /^SOURCE:\s*(.+)$/m, which only matches a
single line because . does not match newlines even with the m flag.

```bash
grep -n "add a one-line source citation\|Never omit it" /home/corby/jamm-os/app/api/concierge/prompts.py
```

Confirm the current SOURCE instruction has no explicit rule against wrapping
the line.

---

## WHAT IS WRONG

Confirmed via live testing: a draft's footnote showed a truncated "Based on:
2025 Individual Tax Return (Marcus" and the email body itself ended with an
orphaned fragment, "& Diana Webb), due 2026-04-15, 1 active engagement on
file." This is one SOURCE sentence that the model wrapped across two lines
in its raw output. The parser regex /^SOURCE:\s*(.+)$/m only captures and
removes the first line. The second line is never recognized as part of the
SOURCE line, so it stays behind in rawBlock and renders as part of the
visible email body.

This needs two fixes, addressing both sides: the parser must not depend on
the model keeping SOURCE on one physical line, and the prompt should also
ask the model not to wrap it, since a long source description is more
readable on one line for the firm owner's own scanning anyway.

---

## ACTION

File 1: `/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx`

In parseDraftFromResponse, replace the SOURCE extraction so it captures
through to the next blank line or the end of rawBlock, not just to the next
single newline:

```typescript
let source: string | null = null
const sourceMatch = rawBlock.match(/SOURCE:\s*([\s\S]+?)(?:\n\s*\n|$)/)
if (sourceMatch) {
  source = sourceMatch[1].replace(/\s+/g, ' ').trim()
  rawBlock = rawBlock.slice(0, sourceMatch.index).trim()
}
```

This removes everything from the start of the SOURCE: marker onward,
regardless of how many lines it spans, and collapses internal line breaks
in the captured source text into single spaces for clean footnote display.

File 2: `/home/corby/jamm-os/app/api/concierge/prompts.py`

In the SOURCE line instruction, add one sentence:
Keep the SOURCE line on a single line of text with no line break in it,

even if it is long.

Place this directly after the existing "Never omit it. Never fabricate a
source" sentence. Do not change anything else in this section. Do not touch
any other file.

---

## VERIFY AFTER ACT

```bash
grep -n "SOURCE:.*\[\\\\s\\\\S\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
```

Expected: the new multi-line-safe regex is present.

```bash
grep -n "no line break in it" /home/corby/jamm-os/app/api/concierge/prompts.py
```

Expected: present.

```bash
cd /home/corby/jamm-os/frontend
npm run build
```

Expected: zero TypeScript errors.

---

## MANUAL VERIFICATION (the actual test)

1. Restart both frontend and backend.
2. Reproduce the original scenario: view Marcus & Diana Webb's page, ask
   for a follow-up email draft.
3. Confirm the email body ends cleanly with no trailing fragment after the
   sign-off, and the "Based on:" footnote shows the complete source
   description on one line with no truncation.
4. If the model still happens to wrap the SOURCE line despite the new prompt
   instruction, confirm the parser fix still produces a clean result anyway,
   since the fix must not depend on the model fully obeying the new
   instruction.

Report what you observe at step 3 specifically.

---

## GIT

```bash
cd /home/corby/jamm-os
git add -A
git commit -m "fix: draft SOURCE line parsing no longer leaks a trailing fragment into the email body when the model wraps the source description across two lines; also instruct the model to keep it on one line"
git pull --rebase origin main
git push origin main
```

If conflicts on task.md use --theirs. Conflicts on source files use --ours.