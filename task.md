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

Task: Add navigation status line to JAMM Concierge autopilot

Read frontend/src/components/concierge/ConciergePanel.tsx in full before writing anything.

Fix 1 — Status message state
Add a statusMessage state variable to ConciergePanel.tsx. Type is string, default is empty string.

Fix 2 — Set status message after every autopilot action
After every emitConciergeAction call, set statusMessage to a human-readable description of what just happened. Use these exact strings:
- Navigation to /clients → "Navigated to Clients"
- Navigation to /clients/[slug] → "Navigated to [client name]"
- Navigation to /settings/team → "Navigated to Team Settings"
- Navigation to /templates → "Navigated to Engagement Templates"
- Navigation to /integrations → "Navigated to Integrations"
- Navigation to /billing → "Navigated to Billing"
- Modal or drawer opened → "Opened [modal name]"

Fix 3 — Auto-clear status message
Add a useEffect that watches statusMessage. When statusMessage is set to a non-empty string, clear it back to empty string after 2000ms. Cancel the timeout on cleanup.

Fix 4 — Render status line
Render the status message below the last assistant response in the chat area. Only render when statusMessage is non-empty. Use a small muted style. Add a Tailwind transition so it fades in on appear and fades out as it clears: use opacity-0 and opacity-100 with transition-opacity duration-500.

After all steps:
1. grep -n "statusMessage\|setStatusMessage" frontend/src/components/concierge/ConciergePanel.tsx
2. grep -n "useEffect" frontend/src/components/concierge/ConciergePanel.tsx
3. grep -n "transition-opacity\|opacity-0\|opacity-100" frontend/src/components/concierge/ConciergePanel.tsx
4. npm run build from frontend directory — zero TypeScript errors
5. Browser test: autopilot ON, "add a client" — status line "Navigated to Clients" appears below response and fades after 2 seconds
6. Browser test: autopilot ON, "create an engagement for Patricia Nguyen" — status line "Navigated to Patricia Nguyen" appears and fades
7. Report exact lines changed

