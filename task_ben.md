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

# Section 3 - The task

# Task: Collapse notification cards behind a toggle, collapsed by default, with a dismiss-all action

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '795,820p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current notifications block structure: the {notifications.length > 0 && (...)} wrapper, the static "N Alerts" header span, and the notifications.map rendering each card in full, always visible, with no expand/collapse state anywhere.

grep -n "dismissNotification" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm dismissNotification(id: string) already exists as a working per-notification dismiss function, so bulk-dismiss can reuse it rather than duplicating its logic.

## WHAT IS WRONG

Confirmed via live testing: when multiple notification cards are present (commonly 2-3, each a full card with message text and sometimes a draft sub-card), they consume roughly half the visible panel height before any actual chat content is reachable. There is currently no way to collapse them, and no way to dismiss all of them at once -- only one at a time via each card's individual X button. This makes the panel feel cluttered and pushes the actual conversation, which is what someone opens the panel for, further down or off-screen.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Add a new state variable near the other panel-level state (alongside notifications, autopilotOn, etc.):

const [notificationsExpanded, setNotificationsExpanded] = useState(false)

Change the "N Alerts" header to a clickable button that toggles this state, and only render the full notification cards when notificationsExpanded is true. When collapsed, show just the header row with a chevron indicating it can expand, plus a "Dismiss all" text action next to it.

Replace the current header block:

            <div className="flex items-center gap-1.5 px-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[#92400E] dark:text-[#D97706]">
                {notifications.length} {notifications.length === 1 ? 'Alert' : 'Alerts'}
              </span>
            </div>
            {notifications.map((n) => {

with:

            <div className="flex items-center justify-between px-0.5">
              <button
                onClick={() => setNotificationsExpanded((prev) => !prev)}
                className="flex items-center gap-1.5"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
                <span className="text-[10px] font-semibold uppercase tracking-wide text-[#92400E] dark:text-[#D97706]">
                  {notifications.length} {notifications.length === 1 ? 'Alert' : 'Alerts'}
                </span>
                <ChevronDown
                  className={`h-3 w-3 text-[#92400E] dark:text-[#D97706] transition-transform ${notificationsExpanded ? 'rotate-180' : ''}`}
                />
              </button>
              {notificationsExpanded && (
                <button
                  onClick={() => notifications.forEach((n) => dismissNotification(n.id))}
                  className="text-[10px] font-medium text-[#6B7280] dark:text-[#9CA3AF] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
                >
                  Dismiss all
                </button>
              )}
            </div>
            {notificationsExpanded && notifications.map((n) => {

Add ChevronDown to the existing lucide-react import at the top of the file (alongside X, Send, Zap, Download).

The map's closing needs a matching change: find where the map block currently closes with just })} and confirm it still closes the conditional correctly once notificationsExpanded && notifications.map(...) wraps it -- the JSX structure should remain valid with this change applied only to the start of the map, not its internals.

Do not change dismissNotification itself, the per-card rendering, the draft sub-card, or any other section of this file. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "notificationsExpanded\|ChevronDown\|Dismiss all" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: all three present.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open the Concierge panel on a session with 2 or more notifications present.
3. Confirm the panel now shows only the collapsed "N Alerts" header by default, with no full cards visible, and the chat content below is immediately reachable.
4. Click the "N Alerts" header, confirm it expands to show all cards exactly as before, with the chevron now pointing up.
5. Click "Dismiss all," confirm every notification disappears and the header section itself disappears entirely (since notifications.length is now 0).
6. Regression check: with notifications expanded, click a single card's individual X button, confirm it still dismisses just that one card and the others remain, exactly as before.
7. Regression check: click into a notification's draft card (Copy / Open to send), confirm that still works exactly as before while expanded.

Report what you observe at steps 3 and 5 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: Concierge notification cards now collapse behind a toggle (collapsed by default) with a dismiss-all action, instead of always rendering every card in full and consuming half the panel height"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.