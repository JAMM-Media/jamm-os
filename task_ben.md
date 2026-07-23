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

TASK: Fix morning briefing detail fetch permanently stuck on restored sessions, and add a timeout with retry instead of silently failing forever

USE: Fable 5

VERIFY BEFORE ACT:
grep -n "detailReady\|setDetailReady\|detailBriefing" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
sed -n '470,500p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Read the full briefing initialization flow and the show_briefing_again handler in full before changing anything, including how messages get restored from sessionStorage on page load.

WHAT IS WRONG:

detailReady is a single, panel-wide boolean starting false on every fresh mount. It is only ever set true by two specific code paths: the very first live briefing generation on a given day, and the explicit show_briefing_again action. Confirmed live: after downloading a briefing successfully once, leaving the app, and returning, the download button showed Preparing report... indefinitely with no way to ever recover, since the restored briefing message went through neither of the two paths that set detailReady true. Separately, even when the detail fetch does fire, its catch block is empty, silently swallowing any real failure with zero retry option and zero indication to the firm owner that anything went wrong, leaving the same permanently stuck pulsing state as the cold path.

CHANGE INSTRUCTIONS:

When a briefing message is restored from sessionStorage on page load (identify this the same way skipReveal already identifies a restored message), and that restored message is a briefing, trigger the same detail fetch used elsewhere, calling /concierge/morning-briefing/detail and setting detailBriefing and detailReady on success, so a returning firm owner does not have to ask to see the briefing again just to make the download button work.

Add a reasonable timeout, such as 15 seconds, starting whenever a detail fetch begins. If detailReady has still not become true by the time the timeout elapses, whether from the restoration path, the first-generation path, or the explicit show again path, transition the button to a clear failed state, such as Could not load report, with a way to retry the fetch on click, rather than leaving the pulsing Preparing report... text showing indefinitely with no recourse. Reuse the existing statusMessage pattern already used elsewhere in this file for similar failure messaging if it fits.

Do not remove or weaken the existing empty catch blocks' safety, silently failing an individual fetch attempt is fine, the requirement is that the user eventually sees a real failure state and a way to retry, not that every possible error gets surfaced immediately.

VERIFY AFTER ACT:

grep -n "detailReady\|setDetailReady\|Could not load report\|retry" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers.

Reproduce the original failure: view a fresh briefing, confirm the download button works and produces a real PDF. Then reload the page entirely, so the briefing message is restored from sessionStorage rather than freshly generated, and confirm the download button now correctly becomes available again within a reasonable time, not stuck on Preparing report... forever.

If possible, simulate a genuine failure, such as briefly stopping the backend before triggering the detail fetch, and confirm the button transitions to a clear failed state with a working retry option after the timeout, rather than pulsing indefinitely.

Report pass or fail individually for the restoration case and the timeout and retry case.

GIT:
git add -A
git commit -m "fix morning briefing download button getting permanently stuck on Preparing report when a briefing message is restored from a past session, since only live generation and explicit show-again previously triggered the detail fetch that unlocks downloading, and add a timeout with a clear failed state and retry option instead of silently pulsing forever on any real fetch failure"
git pull --rebase origin main
git push origin main