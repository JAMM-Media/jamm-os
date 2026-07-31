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
- Never trust file contents shown in VS Code opened against the Windows copy (C:\Users\corby\jamm-os) or Windows File Explorer. Verify all file state via the WSL terminal (cat, ls -la, wc -l) before assuming a file is stale, empty, or correct.
- Generated snapshot files (codebase_snapshot.txt, frontend/frontend_snapshot.txt) are gitignored. Never manually stage, commit, or resurrect them. Regenerate only via ./update_all_snapshots.sh.
- Before the first commit of any session, confirm git config user.email is ben@jammpx.com. Never assume git identity is correct without checking.
- Before writing or modifying anything touching the Concierge agent, read /home/corby/jamm-os/JAMM_PX_Perfect_Assistant_Build.md in full. Every Concierge task should be traceable to something described in that document.
- If a Concierge tool call fails inside the tool-use loop, the failure must surface as a diagnosable logged event, never as a generic deflection presented to the firm owner as if it were a real answer. Check backend logs for "Tool execution failed" before concluding a knowledge gap exists rather than a broken tool call.

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

TASK: Build real Concierge tool coverage for Notes and Firm Chat, fixing a confirmed live fabrication where the Concierge denied Firm Chat exists and stalled on a Notes question

USE: Fable 5

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/app/models/note.py

cat /home/corby/jamm-os/app/models/firm_chat.py

sed -n '145,165p' /home/corby/jamm-os/app/api/concierge/route.py

sed -n '45,55p' /home/corby/jamm-os/app/api/concierge/route.py

grep -n "firm.chat\|firm_chat\|Firm Chat" /home/corby/jamm-os/app/api/concierge/prompts.py /home/corby/jamm-os/app/api/concierge/route.py /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the real fields on Note, firm_id, entity_type, entity_id, author_id, body, is_private, is_deleted, created_at, and on Channel and FirmMessage, firm_id, channel_id, sender_id, body, created_at, is_deleted, with Channel having a name field. Confirm zero existing references to Firm Chat or Notes anywhere in the Concierge's prompts, route, or functions files, confirming this is genuinely new tool coverage, not a routing bug in existing tools.

WHAT THIS IS:

A live browser audit tonight asked the Concierge four real questions about Notes and Firm Chat. One got an honest, correct no-access answer. The other three failed badly: one stalled with "Let me look that up for you" and never delivered an answer, even though the real, correct answer, no notes exist yet for that client, was directly available. Two others flatly denied Firm Chat exists as a feature at all, when it is a real, visible, working page in the same product. This happened because the Concierge has zero tool coverage for either domain, so when asked, it reasons from its own general assumptions rather than real data, and got it wrong with full confidence. This matches the core lesson proven repeatedly tonight: a model with no real data to answer from will eventually guess wrong, and the only real fix is giving it the real data, not a better worded prompt. This task builds two new real, tested tools, matching the exact structure and registration pattern already used for every other tool built tonight.

CHANGE INSTRUCTIONS:

In functions.py, add a new function get_recent_notes(firm_id, db, days=7) that queries the Note table for firm_id matching, is_deleted false, is_private false, created_at within the last N days, ordered newest first, limited to 20. Deliberately exclude private notes entirely, never surface their content or count them, this is a real, deliberate privacy decision, not an oversight. For each note, join to resolve a real author name from the author relationship. When entity_type equals client, attempt to join Client on entity_id to resolve a real client name, matching the exact firm-scoped join pattern already used elsewhere in this file, for example in get_client_document_status. For any other entity_type, return the entity_type and entity_id as-is without a resolved name. Truncate each note's body to a reasonable snippet, for example the first 150 characters, in the returned data, do not return full note bodies. Return a dict with note_count and a list of the notes.

Add a second new function get_recent_firm_chat_activity(firm_id, db, days=7) that queries FirmMessage joined to Channel, filtered to firm_id matching, is_deleted false, created_at within the last N days, ordered newest first, limited to 20. For each message, join to resolve a real sender name and the real channel name. Truncate each message's body to a reasonable snippet, the same style as the notes function. Return a dict with message_count and a list of the messages.

In route.py, import both new functions alongside the existing function imports. Add two new tool schema entries to the tools list, matching the exact style, structure, and description tone of the existing entries, for example get_deadline_calendar's entry, with clear descriptions telling the model when to call each one, for example when the firm owner asks about recent client notes, firm chat activity, team messages, or what has been discussed internally. Add two new elif branches in the tool dispatch matching the exact style of the existing ones, calling each new function with current_firm.id and db.

Do not modify any existing function, tool entry, or dispatch branch, this task only adds two new, additive tool registrations.

VERIFY AFTER ACT:

grep -n "def get_recent_notes\|def get_recent_firm_chat_activity" /home/corby/jamm-os/app/api/concierge/functions.py

grep -n "get_recent_notes\|get_recent_firm_chat_activity" /home/corby/jamm-os/app/api/concierge/route.py

Expected: both functions present, both imported, both registered as tool schema entries, both present in the dispatch block.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

Check whether any real notes or real Firm Chat messages currently exist for this firm. If none exist, real test data should be inserted directly, the same careful way test data was inserted for Timesheets, Staff, and Documents earlier tonight, a real note on a real client and a real message in a real or newly created channel, so the new tools have something real to find.

Re-ask the exact four questions from tonight's audit, one at a time, and report each response verbatim:
"What's in the notes for Robert & Carol Tanner?"
"Has anyone written any client notes recently?"
"What's been said in Firm Chat today?"
"Summarize the most recent Firm Chat messages"

For each, confirm the response now reflects real data if real data exists, or an honest, correct statement that nothing recent exists if it does not, and confirm none of the four responses deny that Firm Chat exists as a feature or stall without delivering an answer.

Report pass or fail for each of the four questions individually, quoting the actual response text.

GIT:

git add -A

git commit -m "build real Concierge tool coverage for Notes and Firm Chat, fixing a confirmed live fabrication found by tonight's browser audit where the Concierge flatly denied Firm Chat exists as a feature and stalled without answering a real notes question, adding get_recent_notes and get_recent_firm_chat_activity as real, tested tools following the exact registration pattern used for every other tool tonight, with private notes deliberately and permanently excluded from what the Concierge can ever surface"

git pull --rebase origin main

git push origin main