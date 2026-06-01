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

Task: Restyle autopilot toggle button and add indicator line in ConciergePanel.tsx

Read frontend/src/components/concierge/ConciergePanel.tsx in full before writing anything.

Fix 1 — Replace the autopilot toggle button

Find the existing autopilot toggle button. Replace it with exactly this:

<button
  onClick={() => setAutopilotOn((v) => !v)}
  title="Autopilot mode. When on, JAMM Concierge will navigate the app and open the right screen for you. You always complete and save the action yourself."
  className={`flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-[4px] border border-[0.5px] transition-all duration-150 ${
    autopilotOn
      ? 'border-[#1F3148] bg-[#1F3148] text-white dark:border-[#4A7FA5] dark:bg-[#4A7FA5]'
      : 'border-[#C8CDD6] dark:border-[#484848] bg-transparent text-[#6B7280] dark:text-[#9CA3AF] hover:border-[#1F3148] hover:text-[#1F3148] dark:hover:border-[#4A7FA5] dark:hover:text-[#4A7FA5]'
  }`}
>
  <Zap className={`h-3 w-3 transition-all ${autopilotOn ? 'fill-white stroke-white' : 'fill-none'}`} />
  Autopilot
</button>

Fix 2 — Add indicator line below the header

Find the header div (the flex div containing the logo, title, autopilot button, and X button). Immediately after the closing tag of that header div, add:

{autopilotOn && (
  <div className="px-4 py-1 bg-[#EBF4FB] dark:bg-[#1a3a52] border-b border-[0.5px] border-[#C8CDD6] dark:border-[#484848]">
    <p className="text-[11px] text-[#4A7FA5] dark:text-[#7ab8d8]">Autopilot on. I'll navigate for you.</p>
  </div>
)}

After all changes:
1. grep -n "Autopilot mode. When on\|navigate for you\|fill-white\|autopilotOn" frontend/src/components/concierge/ConciergePanel.tsx
2. sed -n between the autopilot button onClick line and 20 lines after it — print the exact block
3. npm run build from frontend directory — zero TypeScript errors
4. Browser test: confirm tooltip text appears on hover, ON state is dark navy filled, OFF state is outline, indicator line appears below header when on
5. Report exact lines changed