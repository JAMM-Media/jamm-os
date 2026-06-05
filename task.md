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

TASK: Stream post-processor for text artifacts -- ConciergePanel.tsx

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before stream post-processor"

VERIFY BEFORE ACT:
grep -n "filterOutput\|function filter" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Paste output before touching anything.

---

Change 1: Add text normalization to filterOutput function

Find exactly:
  function filterOutput(text: string): string {
    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g
    const EIN_PATTERN = /\b\d{2}-\d{7}\b/g
    const LEAK_PHRASES = [

Add a normalizeText call at the very start of filterOutput, and add the
normalizeText function immediately before filterOutput.

Find exactly:
  function filterOutput(text: string): string {

Add this block immediately before it:

  function normalizeText(text: string): string {
    // Collapse spaces before punctuation (streaming token boundary artifact)
    // "word ." -> "word."   "word ," -> "word,"   "word :" -> "word:"
    text = text.replace(/ ([.,;:!?])/g, '$1')

    // Collapse spaces inside IRS form numbers and common numeric strings
    // "8 821" -> "8821"   "2 848" -> "2848"   "1 040" -> "1040"
    text = text.replace(/\b(\d{1,4})\s(\d{3,4})\b/g, '$1$2')

    // Collapse spaces around hyphens in known compound terms
    // "magic -link" -> "magic-link"   "book- keeping" -> "bookkeeping"
    text = text.replace(/(\w+)\s+-\s*(\w+)/g, '$1-$2')
    text = text.replace(/(\w+)-\s+(\w+)/g, '$1-$2')

    // Normalize known compound terms that must never be split
    const COMPOUND_TERMS: [RegExp, string][] = [
      [/magic\s*-?\s*link/gi, 'magic-link'],
      [/quick\s*books/gi, 'QuickBooks'],
      [/book\s*keeping/gi, 'bookkeeping'],
      [/on\s*board\s*ing/gi, 'onboarding'],
      [/auto\s*pilot/gi, 'Autopilot'],
    ]
    for (const [pattern, replacement] of COMPOUND_TERMS) {
      text = text.replace(pattern, replacement)
    }

    // Normalize IRS form numbers -- never split these
    const FORM_NUMBERS: [RegExp, string][] = [
      [/\b8\s*8\s*2\s*1\b/g, '8821'],
      [/\b2\s*8\s*4\s*8\b/g, '2848'],
      [/\b1\s*0\s*4\s*0\b/g, '1040'],
      [/\b1\s*1\s*2\s*0\b/g, '1120'],
      [/\b1\s*0\s*6\s*5\b/g, '1065'],
      [/\b1\s*1\s*2\s*0\s*[Ss]\b/g, '1120-S'],
      [/\b9\s*4\s*1\b/g, '941'],
      [/\b9\s*4\s*0\b/g, '940'],
      [/\b1\s*0\s*9\s*9\b/g, '1099'],
      [/\b1\s*0\s*9\s*8\s*[Tt]\b/g, '1098-T'],
      [/\b W\s*-\s*2\b/gi, 'W-2'],
      [/\b W\s*-\s*9\b/gi, 'W-9'],
    ]
    for (const [pattern, replacement] of FORM_NUMBERS) {
      text = text.replace(pattern, replacement)
    }

    // Collapse double spaces
    text = text.replace(/ {2,}/g, ' ')

    return text
  }

Then find the opening line of filterOutput and add the normalizeText call:

Find exactly:
  function filterOutput(text: string): string {
    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g

Replace with:
  function filterOutput(text: string): string {
    // Normalize streaming artifacts before any other checks
    text = normalizeText(text)

    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g

Do not change anything else.

VERIFY AFTER ACT:
grep -n "normalizeText\|COMPOUND_TERMS\|FORM_NUMBERS\|magic-link\|QuickBooks\|8821" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Confirm all six terms appear.

Post-task:
cd /home/corby/jamm-os/frontend
npm run build
Zero TypeScript errors required before stopping.

Browser tests:
Test 1 -- Form numbers:
  Type: "what is the difference between an 8821 and a 2848"
  Confirm response contains 8821 and 2848 with no spaces inserted

Test 2 -- Compound terms:
  Type: "how do I send a magic-link to a client"
  Confirm response contains "magic-link" not "magic -link" or "magic- link"

Test 3 -- Punctuation spacing:
  Send any multi-sentence response and read carefully
  Confirm no spaces before periods or commas

Test 4 -- Normal flow:
  Type: "how do I add a client"
  Confirm response is clean and unaffected