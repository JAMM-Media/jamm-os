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

Task: Add current page context pill to input bar in ConciergePanel.tsx

VERIFY BEFORE ACT:
Run this and paste the full output:
grep -n "usePathname\|pathname\|input.*bar\|Ask anything" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -20

Paste before touching anything.

Add a context pill above the input bar that shows the current page the user is on.

Changes needed:

1. Import usePathname at the top of the file:
import { usePathname } from 'next/navigation'

2. Add pathname inside the component:
const pathname = usePathname()

3. Add a label map:
const PAGE_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/clients': 'Clients',
  '/engagements': 'Engagements',
  '/tasks': 'Tasks',
  '/documents': 'Documents',
  '/billing': 'Billing',
  '/settings': 'Settings',
  '/firm-chat': 'Firm Chat',
}
const currentPage = Object.entries(PAGE_LABELS).find(([k]) => pathname.startsWith(k))?.[1] ?? 'JAMM PX'

4. Add the pill just above the input bar div:
{currentPage && (
  <div className="px-3 pt-2 pb-0">
    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-[#6B7280] dark:text-[#9CA3AF]">
      <span className="w-1.5 h-1.5 rounded-full bg-[#4A7FA5]" />
      You are on: {currentPage}
    </span>
  </div>
)}

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "usePathname\|currentPage\|You are on" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
2. Confirm all three are present
3. cd /home/corby/jamm-os/frontend
4. npm run build — zero TypeScript errors
5. Report exact changes made