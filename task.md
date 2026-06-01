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

# PRE-TASK
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

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

Task: Improve autopilot tooltip styling in ConciergePanel.tsx

Read frontend/src/components/concierge/ConciergePanel.tsx in full before writing anything.

Find this exact div:
<div className="absolute right-0 top-8 z-50 hidden group-hover:block w-56 rounded-[6px] bg-[#1F3148] text-white text-[11px] leading-[1.5] px-3 py-2 shadow-lg">

Replace it with:
<div className="absolute right-0 top-9 z-50 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity duration-150 w-60 rounded-[8px] bg-[#1F3148] text-white text-[11px] leading-[1.6] px-4 py-3 shadow-xl">
  <div className="absolute -top-1.5 right-4 w-3 h-3 bg-[#1F3148] rotate-45 rounded-sm" />

Do not remove the closing </div> of the tooltip. Do not change any other part of the file.

After the change:
1. grep -n "rounded-\[8px\]\|opacity-0\|rotate-45\|top-9" frontend/src/components/concierge/ConciergePanel.tsx
2. sed -n between the tooltip div line and 5 lines after it
3. npm run build from frontend directory — zero TypeScript errors
4. Report exact lines changed