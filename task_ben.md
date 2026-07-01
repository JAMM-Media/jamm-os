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

# Task: Fix reveal stutter by preventing ReactMarkdown from parsing malformed mid-token markdown during word-by-word reveal

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '1038,1058p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current reveal slice: msg.content.split(/\s+/).filter(Boolean).slice(0, revealedWordCount).join(' ') is passed directly into ReactMarkdown with no sanitization, meaning a bold span like **Portal Branding** can be sliced mid-phrase (e.g. after "Portal" but before the closing **), producing an unclosed markdown token that ReactMarkdown attempts to parse on every reveal frame.

## WHAT IS WRONG

Confirmed via live testing: the reveal stutter got measurably worse after adding markdown formatting instructions to the system prompt. Root cause: the word-slicing logic used for the reveal animation operates on raw markdown source text with no awareness of markdown syntax. When the revealed word count lands inside a bold span (e.g. **Portal Branding** where "Portal" is one word and "Branding**" is the next), the sliced string contains an unclosed emphasis marker like "...Navigate to **Portal". ReactMarkdown must attempt to parse this malformed inline markdown on every single animation frame during the reveal, which is measurably more expensive than parsing clean, syntactically valid text, and is a plausible primary contributor to the observed freeze -- more so than raw render frequency alone.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Add a helper function near the top of the component (or as a module-level function above the component) that sanitizes a word-sliced string by removing any trailing unclosed bold marker:

function sanitizeRevealSlice(text: string): string {
  const asteriskCount = (text.match(/\*\*/g) || []).length
  if (asteriskCount % 2 !== 0) {
    const lastIndex = text.lastIndexOf('**')
    return text.slice(0, lastIndex)
  }
  return text
}

This counts occurrences of ** in the sliced text. An odd count means the last ** opened a bold span that has not been closed yet within the current reveal window. In that case, truncate the string at the position of that unclosed marker, so the bold span simply has not started yet from the renderer's perspective, rather than being left half-open. Once enough words have revealed to include the closing **, the count becomes even again and the full bold span renders normally.

Apply this function to the existing reveal slice:

Change:

                      {streaming && i === messages.length - 1
                        ? msg.content.split(/\s+/).filter(Boolean).slice(0, revealedWordCount).join(' ')
                        : msg.content}

To:

                      {streaming && i === messages.length - 1
                        ? sanitizeRevealSlice(msg.content.split(/\s+/).filter(Boolean).slice(0, revealedWordCount).join(' '))
                        : msg.content}

Do not change the reveal timing logic, the requestAnimationFrame effect, or any other part of the streaming or reveal mechanism. Do not change the ReactMarkdown components configuration. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "sanitizeRevealSlice" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: the function definition and its use in the reveal slice, both present.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Ask "how do I customize my client portal colors?" again -- the response with heavy bold usage that showed the worst stutter.
3. Confirm the reveal is now smooth with no visible freeze, even through the bold phrases like "Portal Branding", "Set as active", "Save branding", "Reset to defaults".
4. Confirm bold text still renders correctly once each phrase fully reveals -- no missing or stuck-unbolded text in the final rendered message.
5. Ask "where are my clients?" again -- confirm short responses still reveal smoothly.

Report what you observe at steps 3 and 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: reveal animation now sanitizes word-sliced content to avoid feeding ReactMarkdown unclosed bold markers mid-reveal, which was forcing expensive malformed-markdown parsing on every animation frame and was the likely primary cause of the stutter on bold-heavy responses"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.