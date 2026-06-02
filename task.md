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

# Section 3: Task to perform

Task: Add action suggestion chips after concierge responses in ConciergePanel.tsx

VERIFY BEFORE ACT:
Run this and paste the full output:
grep -n "assembled\|setMessages\|role.*concierge\|autopilotOn" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | tail -30

Paste before touching anything.

After each concierge response renders, show 2-3 tappable action chips below the bubble when autopilot is ON. These chips suggest the next logical action based on the response content.

Changes needed:

1. Add a suggestions state:
const [suggestions, setSuggestions] = useState<string[]>([])

2. After the full response is assembled and set, generate suggestions. Use a simple keyword match on the assembled string:
- If assembled includes "client" or "import" → suggest "Go to Clients", "Import clients"
- If assembled includes "engagement" → suggest "Go to Engagements", "New engagement"
- If assembled includes "settings" or "team" or "staff" → suggest "Go to Settings"
- If assembled includes "billing" or "invoice" or "stripe" → suggest "Go to Billing"
- If assembled includes "document" → suggest "Go to Documents"
- Default → suggest "Go to Dashboard"
Always limit to maximum 3 chips.

3. Render chips below the last concierge message bubble when autopilotOn is true and suggestions.length > 0:
<div className="flex flex-wrap gap-2 mt-2 ml-8">
  {suggestions.map((s) => (
    <button
      key={s}
      onClick={() => handleSuggestion(s)}
      className="text-[11px] font-medium px-3 py-1.5 rounded-full border border-[#C8CDD6] dark:border-[#484848] text-[#1F3148] dark:text-[#EDEEF0] bg-white dark:bg-[#2D2D2D] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
    >
      {s}
    </button>
  ))}
</div>

4. Add handleSuggestion function that navigates using the existing router:
- "Go to Clients" → router.push('/clients')
- "Go to Engagements" → router.push('/engagements')
- "Go to Settings" → router.push('/settings')
- "Go to Billing" → router.push('/billing')
- "Go to Documents" → router.push('/documents')
- "Go to Dashboard" → router.push('/dashboard')
- "Import clients" → router.push('/clients')
- "New engagement" → router.push('/engagements')

5. Clear suggestions when user sends a new message.

Do not change anything outside these additions.

VERIFY AFTER ACT:
1. grep -n "suggestions\|handleSuggestion\|chips" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -20
2. cd /home/corby/jamm-os/frontend
3. npm run build — zero TypeScript errors
4. Report exact changes made