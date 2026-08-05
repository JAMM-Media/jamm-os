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

TASK: Fix three real topic-chip issues found by tonight's audit: an imprecise Staff chip label, suppressed nav chips when per-client options are present, and missing chips for client-overview questions

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '415,440p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '560,575p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

sed -n '317,323p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm 'Go to Staff': '/staff' already exists and works correctly in the chip-to-route mapping table, and confirm TOPIC_CHIPS currently maps the staff topic to 'Go to Dashboard' instead, meaning the correct destination already exists and is simply never used for this topic. Confirm the current suggestion-suppression condition is parsedResult || parsedOptions.length > 0, meaning topic chips are hidden any time real per-client option buttons are present, not only when a full draft exists. Confirm _TOPIC_KEYWORDS["clients"] in route.py currently has no phrases matching general client-overview questions like tell me about a client.

WHAT THIS IS:

Three real, separately confirmed topic-chip issues from a live browser audit tonight. First, the staff topic's chip says Go to Dashboard even though a real, correct Go to Staff destination already exists and works, simply never referenced. Second, asking about overdue invoices or stalled engagements produces real, correct per-client option buttons but no Go to Billing or Go to Engagements chip at all, because the current logic treats any presence of per-client options the same as a full draft and suppresses topic chips entirely, when in reality a general navigation chip and specific per-client action buttons serve different purposes and can reasonably coexist. Third, asking to tell me about a specific client produces no chip at all, because this phrasing is not recognized by the same topic classification system already used for chip selection, so it falls into the general topic, which intentionally has no chips.

CHANGE INSTRUCTIONS:

In ConciergePanel.tsx, change TOPIC_CHIPS's staff entry from ['Go to Dashboard'] to ['Go to Staff'], since the correct route mapping already exists and works.

In the same file, change the suggestion-suppression condition from parsedResult || parsedOptions.length > 0 to just parsedResult, so topic chips continue to be suppressed when a full draft is present, since taking an action mid-draft is a different case, but are no longer suppressed just because per-client option buttons are present, allowing a real navigation chip and specific per-client options to appear together.

In route.py, add the same real client-overview phrases already added earlier tonight to _OPERATIONAL_KEYWORDS, for example tell me about, give me an overview, client overview, client summary, client snapshot, what's going on with, summarize this client, pull up their, pull up this client, to _TOPIC_KEYWORDS["clients"] as well, matching the exact existing style of that set, so these questions are now classified into the clients topic and receive the existing Go to Clients chip instead of no chip at all.

VERIFY AFTER ACT:

grep -n "staff: \['Go to Staff'\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "parsedResult ? \[\] : \|setSuggestions(parsedResult ?" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "tell me about" /home/corby/jamm-os/app/api/concierge/route.py

npx tsc --noEmit

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart both servers.

Ask "Which staff members are overloaded?" Confirm the chip now reads Go to Staff and correctly navigates to the Staff page, not Dashboard.

Ask "How many overdue invoices do I have?" Confirm the response still shows real, correct per-client option buttons, and now also shows a Go to Billing chip alongside them.

Ask "Which engagements are stalled?" Confirm the response still shows real, correct per-client option buttons, and now also shows a Go to Engagements chip alongside them, without needing to click into a client first.

Ask "Tell me about Robert & Carol Tanner." Confirm a Go to Clients chip now appears where none did before.

Report pass or fail for each of these four checks individually.

GIT:

git add -A

git commit -m "fix three real topic-chip issues confirmed by tonight's audit: correct the staff topic's chip label from Go to Dashboard to Go to Staff, since the correct route mapping already existed and was simply never used; stop suppressing topic navigation chips whenever per-client option buttons are present, since a general navigation chip and specific per-client actions serve different purposes and can coexist, only a full draft should suppress the chip; and add the same client-overview phrases already added to the operational keyword gate earlier tonight to the separate topic classification keywords, so questions like tell me about a client now correctly receive a Go to Clients chip instead of none at all"

git pull --rebase origin main

git push origin main