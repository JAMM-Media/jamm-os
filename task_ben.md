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

TASK: Expose the real created_at field on UserOut, fixing the Staff page's Invalid Date bug

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '145,155p' /home/corby/jamm-os/app/models/user.py

sed -n '30,40p' /home/corby/jamm-os/app/schemas/user.py

Confirm User already has a real created_at column, a real Mapped[datetime] field, and confirm UserOut currently has no created_at field at all, despite model_config already being set to ConfigDict(from_attributes=True), meaning this is a pure, safe, additive schema fix, not a data or logic change.

WHAT THIS IS:

Confirmed by a live browser audit tonight: the Staff page's Member Since column shows the literal text Invalid Date for every single row. Traced directly to its real cause: the frontend calls GET /users, whose response model is UserOut, and passes whatever comes back through new Date(member.created_at).toLocaleDateString(). Since UserOut never exposed created_at at all, the frontend received undefined for every user, and new Date(undefined) produces an Invalid Date object in JavaScript, which renders as the literal string seen in the audit. The real data has existed on the User model the entire time, it was simply never included in this response.

CHANGE INSTRUCTIONS:

Add created_at: datetime as a new field to UserOut in schemas/user.py, matching the exact style of the other fields already present. Import datetime at the top of this file if it is not already imported. Do not add any manual assignment logic anywhere, since from_attributes is already enabled, this field will be read directly and automatically from the real User model object.

VERIFY AFTER ACT:

grep -n "created_at" /home/corby/jamm-os/app/schemas/user.py

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

Visit the Staff page. Confirm every row in the Member Since column now shows a real, correctly formatted date instead of Invalid Date.

Report pass or fail.

GIT:

git add -A

git commit -m "expose the real created_at field on UserOut, fixing the Staff page's Member Since column showing the literal text Invalid Date for every row, confirmed by a live browser audit tonight and traced to the real User.created_at column having existed the entire time but never being included in the GET /users response the Staff page actually calls"

git pull --rebase origin main

git push origin main