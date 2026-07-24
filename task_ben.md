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

TASK: Add a closing offer-to-help line to short factual answers, matching the pattern already proven to work

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '12,35p' /home/corby/jamm-os/app/api/concierge/prompts.py
grep -n "Want me to help\|want me to draft\|Would you like" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the current RESPONSE FORMAT section and confirm whether this closing pattern already exists anywhere else in the prompt before writing a new instruction.

WHAT THIS IS:

An independent live audit of the actual running product specifically flagged short, purely factual multi-item answers, such as a bulleted list of overdue invoices with no draft attached, as reading like a database query result rather than an attentive colleague, scoring this the lowest of nine rated dimensions. The same audit specifically identified one existing response, ending with want me to help you work through any of those, as the single strongest attentive colleague moment observed in the entire session, and recommended extending exactly that pattern to every short factual answer rather than inventing new language from scratch. Separately, external research on the psychology of trust and warmth in professional software found that warmth needs to be paired with genuine usefulness or forward motion, not just friendly wording, to avoid reading as hollow, which is exactly what a bare closing offer to help accomplishes here, it points toward real next action, it does not just add friendly filler.

CHANGE INSTRUCTIONS:

Add a new rule to the RESPONSE FORMAT section: whenever a response presents a factual, multi item list, such as overdue invoices, stalled engagements, outstanding tasks, or similar, and does not already end with a draft offer, an OPTIONS marker, or an existing closing question, it should end with one brief, natural closing line either offering to help with the most obvious next action, drafting something, checking further, or similar, or highlighting the single most relevant fact among the items just listed. Give a concrete example directly in the rule, matching the real observed phrasing, such as want me to help you work through any of those, so the model has a genuine reference point rather than inventing generic friendliness. State plainly that this should feel like a natural, specific offer tied to what was just shown, not a generic tacked on phrase repeated identically every time.

Do not apply this to responses that already end with a draft, an OPTIONS marker, or an existing question, this is specifically for the currently cold case, a plain factual list with no follow up at all.

VERIFY AFTER ACT:

grep -n "want me to help you work through\|closing line" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

MANUAL VERIFICATION:

Restart backend. Ask which clients have overdue invoices right now, confirm the response now ends with a natural, specific closing line rather than stopping cold after the list. Ask a similar factual question about stalled engagements or outstanding tasks, confirm the same pattern holds. Separately, ask a question likely to trigger the existing OPTIONS marker for multiple qualifying clients, confirm this new closing line does not stack on top of or interfere with the existing required OPTIONS marker behavior already established earlier tonight.

Report pass or fail for all three.

GIT:
git add -A
git commit -m "add a closing offer-to-help line to short factual multi-item answers, extending the exact pattern an independent live audit identified as the strongest attentive-colleague moment in the product to the cold, database-query-style answers it specifically flagged as the lowest scoring dimension in a nine dimension trust and engagement review"
git pull --rebase origin main
git push origin main