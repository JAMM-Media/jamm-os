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

TASK: Add diagnostic logging to the reveal system, third distinct trigger found tonight, do not fix yet

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '160,195p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "revealSessionRef\|revealActiveRef" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm current state matches before editing.

WHAT THIS IS:

This is a diagnostic task, not a fix. A third distinct trigger for the same blank-display symptom has now been found tonight: a single normal question, asked at normal pace, not rapid fire, displayed permanently blank until a completely new message was sent, at which point the answer appeared immediately. Two prior triggers were already found and fixed tonight, a target-word-count-still-zero timing issue and a rapid-fire session race condition. This third trigger does not match either known cause exactly, since it happened on a single normal question with no rapid sequential messages involved. Rather than guess at a third distinct root cause blind, add logging to observe what actually happens the next time this is reproduced.

CHANGE INSTRUCTIONS:

Add console.log statements clearly prefixed with [REVEAL DEBUG] at these points: when the reveal effect instance starts, log the revealSession value and revealSessionRef.current value at that exact moment, and whether they match. Inside tick, log count, target, and both session values on the first frame only and then once every 20 frames afterward, not every frame. Log whenever revealActiveRef.current changes and what set it. Log whenever the effect's cleanup function actually runs and what revealSession value it belonged to. Specifically also log the exact value of targetWordCountRef.current at the moment the reveal effect first starts, since a mismatch between when the target effect and the reveal effect actually run relative to each other, not just a one-time zero at the very first frame, is a plausible explanation for a session that never catches up until an unrelated event forces a rerender.

Do not attempt to fix the underlying issue in this task. Only add logging around the existing logic exactly as it stands.

VERIFY AFTER ACT:

grep -n "REVEAL DEBUG" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full restart, open browser console filtered to REVEAL DEBUG. Ask a single normal question at normal pace and wait. If it displays correctly, try several more single questions, one at a time, with normal pauses, until the blank state reproduces again. The moment it reproduces, copy the full console output from that specific question's session start through the point a new message was sent, and report that full output back, do not summarize it.

Do not commit or push yet. This is temporary instrumentation, wait for the console output to be reviewed before deciding on a real fix.