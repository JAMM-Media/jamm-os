 STANDING RULES
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

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK — run before touching anything
git add -A
git commit -m "checkpoint before autopilot 3B fixes"
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.

---

# Standing verification rules — apply to every step in this task:
- Never report a file as created without running ls -la on it and including the output
- Never report a fix as working without running grep to confirm the change landed and including the output
- If any verification fails, fix it before moving to the next step
- After all steps, run: python3 -c "from app.api.concierge.route import router; print('OK')"
- Include all verification output in your final summary

---

# POST-TASK — run after task completes
find app/api/concierge/ -name "*.py" | sort
ls migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Section 3: Task to perform

Task: Fix JSX parse error in ConciergePanel.tsx

Read frontend/src/components/concierge/ConciergePanel.tsx in full before writing anything.

The file has a JSX parse error reported at line 511. The error is "Expression expected" near the closing fragment </>. This is caused by an unbalanced JSX tag somewhere in the file.

Do the following:
1. Read the entire file
2. Count every opening and closing div, button, span, and fragment tag to find the mismatch
3. Fix the unbalanced tag — add or remove exactly what is needed to balance the JSX tree
4. Do not change any logic, styling, or content. Only fix the structural balance.

After fixing:
1. npm run build from frontend directory — must show zero TypeScript errors and zero parse errors
2. grep -n "autopilotOn\|relative group\|justify-center" frontend/src/components/concierge/ConciergePanel.tsx
3. sed -n '370,425p' frontend/src/components/concierge/ConciergePanel.tsx — print the full header block to confirm structure is intact
4. Report exactly which line was added or removed and what it was