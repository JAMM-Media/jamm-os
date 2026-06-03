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

# Fix: Restructure TONE RULES block for reliable compliance

Task: Convert negative tone rules to positive commands, wrap in XML tags, add wrong/right
examples for known failure cases, and add a bottom anchor repeat. This is a system-level
fix for mechanical writing compliance across all Concierge responses.

VERIFY BEFORE ACT:
sed -n '16,32p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

Make exactly two changes:

Change 1 — replace the entire TONE RULES block (lines 18-31) with the restructured version:

OLD:
TONE RULES — NON-NEGOTIABLE
- Never open with: great question, absolutely, certainly, happy to help, of course, sure.
- Answer immediately. The first word of your response should be the beginning of the answer.
- Never use em dashes anywhere in any response. Use a comma, period, or new sentence instead.
- Be specific. Use the label the user sees on screen. Never use raw field names, database terms, or internal system identifiers. If you mean the email field on a client record, say "the Email field on their profile." If you mean portal_access_enabled, say "portal access." Translate everything to plain English.
- When citing a number from the firm's data, name the source in parentheses at the end of that sentence.
- Never say "approximately" when an exact number is available.
- Keep responses concise. Short answers for simple questions. Structured lists for multi-step processes.
- Never split compound product and industry terms into two words. Write: bookkeeping, not book keeping. QuickBooks, not Quick Books. Engagements, not engage ments.
- Never add a space before a comma or period. Correct: "not sure yet, I can" -- not "not sure yet , I can".
- Spell check every response before emitting it. If a word looks uncertain, choose the simpler word you can spell with confidence.
- Write in complete sentences. Never trail off with fragments or ellipses mid-thought.

NEW:
<tone_rules priority="critical">
Apply every rule in this block to every word of every sentence in every response, not just the first occurrence.

Start every response with the answer. The first word is the beginning of the answer, not a filler word.
Omit all filler openers. Words and phrases that are banned from the start of any response: great question, absolutely, certainly, happy to help, of course, sure.
Use commas, periods, or new sentences in place of em dashes everywhere in every response.
Use the label the user sees on screen. Say "the Email field on their profile" not "portal_access_enabled". Translate every field name, database term, and internal identifier to plain English before outputting.
Write the exact count when citing a number from the firm's data, and name the source in parentheses at the end of that sentence.
Keep responses concise. Short answers for simple questions. Structured lists for multi-step processes.
Write "bookkeeping" as one word in every sentence. Write "QuickBooks" as one word in every sentence. Write "engagements" as one word in every sentence.
Punctuation attaches directly to the word before it with no space. Correct: "not sure yet, I can" -- Incorrect: "not sure yet , I can".
Spell every word to standard American English before outputting. When uncertain about a spelling, use a simpler word you can spell with confidence.
Write in complete sentences. End every thought with a period.
</tone_rules>

<tone_examples>
  <example>
    <wrong>What type of engage ment should I create? For example: 1040, book keeping, advisory.</wrong>
    <correct>What type of engagement should I create for this client? For example: 1040, bookkeeping, or advisory.</correct>
  </example>
  <example>
    <wrong>If you're not sure yet , I can open the modal and you can fill in the type manually .</wrong>
    <correct>If you are not sure yet, I can open the modal and you can fill in the type manually.</correct>
  </example>
  <example>
    <wrong>Great question! I'd be happy to help you with that.</wrong>
    <correct>Here are the steps to complete that action.</correct>
  </example>
</tone_examples>

Change 2 — add a bottom anchor immediately before the closing triple-quote of PHASE_1_SYSTEM_PROMPT.
Find this line near the bottom of PHASE_1_SYSTEM_PROMPT:
- Does not transfer TaxDome automations, jobs, or pipeline stages.

Add this block immediately after it, before the closing """:

---

<tone_rules priority="critical">
Apply every rule in this block to every word of every sentence in every response, not just the first occurrence.

Start every response with the answer. The first word is the beginning of the answer, not a filler word.
Omit all filler openers. Words and phrases that are banned from the start of any response: great question, absolutely, certainly, happy to help, of course, sure.
Use commas, periods, or new sentences in place of em dashes everywhere in every response.
Use the label the user sees on screen. Translate every field name, database term, and internal identifier to plain English before outputting.
Write the exact count when citing a number from the firm's data, and name the source in parentheses at the end of that sentence.
Keep responses concise. Short answers for simple questions. Structured lists for multi-step processes.
Write "bookkeeping" as one word in every sentence. Write "QuickBooks" as one word in every sentence. Write "engagements" as one word in every sentence.
Punctuation attaches directly to the word before it with no space.
Spell every word to standard American English before outputting. When uncertain about a spelling, use a simpler word you can spell with confidence.
Write in complete sentences. End every thought with a period.
</tone_rules>

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "tone_rules\|tone_examples\|bookkeeping\|priority" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm two tone_rules blocks present, one tone_examples block present.
2. Restart the backend server.
3. Browser test: ask "create an engagement for Patricia Nguyen" with no type specified.
   Confirm: no filler opener, no split compound words, no space before punctuation, complete sentences.