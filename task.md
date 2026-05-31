# STANDING RULES
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

Before starting: git add -A && git commit -m "checkpoint before [task name]"
If anything breaks: git checkout . to restore

---

# Standing verification rules — apply to every step in this task:
- Never report a file as created without running ls -la on it and including the output
- Never report a fix as working without running grep to confirm the change landed and including the output
- If any verification fails, fix it before moving to the next step
- After all steps, run: python3 -c "from app.api.concierge.route import router; print('OK')"
- Include all verification output in your final summary

---

# Section 3: Task to perform

Task: Fix three autopilot issues — panel closes on navigation, client resolver fails, modals not opening

Read frontend/src/components/concierge/ConciergePanel.tsx and frontend/src/lib/events/conciergeEvents.ts in full before writing anything.

Fix 1 — Panel stays open on navigation
The panel closes when autopilot fires a navigation action. It must stay open. Find where router.push() is called after an action fires in ConciergePanel.tsx. Remove any logic that closes the panel when a navigation action fires. The panel should only close when the user clicks X.

Fix 2 — Client resolver slug decoding
The resolver at GET /concierge/clients/resolve?name= fails for "Patricia Nguyen". In ConciergePanel.tsx, find where the slug is extracted from the action route before calling the resolver. The slug may have hyphens instead of spaces. Add: replace hyphens with spaces and apply decodeURIComponent before passing to the resolver. In app/api/concierge/route.py, find the resolve endpoint and change the query to use LOWER(name) LIKE LOWER('%' || :name || '%').

Fix 3 — Modal timing
Actions 1, 5, and 7 navigate but the modal never opens because the event fires before the target page mounts its listener. In ConciergePanel.tsx, find where emitConciergeAction is called after router.push(). Wrap it in a 500ms delay: setTimeout(() => emitConciergeAction(action), 500).

Fix 4 — Autopilot off nudge
When autopilot is off and the model includes a CONCIERGE_ACTION: line in the response, replace the displayed response with: "To use autopilot navigation, turn on Autopilot using the toggle above." The CONCIERGE_ACTION line must be stripped from displayed text regardless of autopilot state.

After all steps:
1. grep -n "isOpen\|setIsOpen\|router.push" frontend/src/components/concierge/ConciergePanel.tsx | head -20
2. grep -n "resolve\|LOWER\|LIKE" app/api/concierge/route.py
3. grep -n "setTimeout\|emitConciergeAction" frontend/src/components/concierge/ConciergePanel.tsx
4. grep -n "autopilot\|CONCIERGE_ACTION" frontend/src/components/concierge/ConciergePanel.tsx | head -20
5. python3 -c "from app.api.concierge.route import router; print('OK')"
6. npm run build from frontend directory — zero TypeScript errors
7. Browser test: autopilot ON, "add a client" — panel stays open, New Client modal opens
8. Browser test: "create an engagement for Patricia Nguyen" — navigates, drawer opens
9. Report exact lines changed in each file