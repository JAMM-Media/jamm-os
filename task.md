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

# Fix: Add 48-hour dismiss cooldown to trigger dedup logic

Task: Triggers re-fire immediately after dismiss because the dedup check only looks for
unread notifications. Add a dismissed_at timestamp to ConciergeNotification and update
the dedup logic to suppress re-firing within 48 hours of dismissal.

Four files. Do them in order. Do not move to the next until the verify step passes.

---

## File 1 of 4: concierge_notification.py

Task: Add dismissed_at column to the model.

VERIFY BEFORE ACT:
grep -n "is_read\|dismissed\|created_at" /home/corby/jamm-os/app/models/concierge_notification.py

Paste before touching anything.

OLD:
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(

NEW:
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(

Do not change anything else.

VERIFY AFTER ACT:
grep -n "dismissed_at" /home/corby/jamm-os/app/models/concierge_notification.py
Confirm one result.

---

## File 2 of 4: Alembic migration

Task: Create a migration to add the dismissed_at column.

VERIFY BEFORE ACT:
ls /home/corby/jamm-os/alembic/versions/ | tail -5

Paste before touching anything.

Run:
cd /home/corby/jamm-os
source .venv/bin/activate
alembic revision --autogenerate -m "add_dismissed_at_to_concierge_notifications"

VERIFY AFTER ACT:
1. ls /home/corby/jamm-os/alembic/versions/ | tail -3
   Confirm new migration file exists.
2. cat the new migration file and confirm it adds dismissed_at as a nullable DateTime column.
3. alembic upgrade head
   Confirm migration applies with no errors.

---

## File 3 of 4: route.py

Task: Set dismissed_at when a notification is marked read.

VERIFY BEFORE ACT:
grep -n "is_read\|dismissed_at" /home/corby/jamm-os/app/api/concierge/route.py

Paste before touching anything.

OLD:
    notification.is_read = True
    db.commit()
    return {"ok": True}

NEW:
    notification.is_read = True
    notification.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}

Also add datetime and timezone to the imports at the top of route.py if not already imported.
Run:
grep -n "from datetime" /home/corby/jamm-os/app/api/concierge/route.py

If missing, add:
from datetime import datetime, timezone

Do not change anything else.

VERIFY AFTER ACT:
grep -n "dismissed_at\|datetime" /home/corby/jamm-os/app/api/concierge/route.py
Confirm dismissed_at is set in the mark_notification_read function.

---

## File 4 of 4: cron.py

Task: Update dedup logic to suppress re-firing within 48 hours of dismissal.

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/app/api/concierge/cron.py

Paste before touching anything.

OLD:
from datetime import datetime, timezone

NEW:
from datetime import datetime, timezone, timedelta

OLD:
        existing = db.execute(
            select(ConciergeNotification).where(
                ConciergeNotification.firm_id == firm_id,
                ConciergeNotification.trigger_type == trigger_type,
                ConciergeNotification.is_read == False,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

NEW:
        existing = db.execute(
            select(ConciergeNotification).where(
                ConciergeNotification.firm_id == firm_id,
                ConciergeNotification.trigger_type == trigger_type,
                ConciergeNotification.is_read == False,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        recently_dismissed = db.execute(
            select(ConciergeNotification).where(
                ConciergeNotification.firm_id == firm_id,
                ConciergeNotification.trigger_type == trigger_type,
                ConciergeNotification.is_read == True,
                ConciergeNotification.dismissed_at >= datetime.now(timezone.utc) - timedelta(hours=48),
            )
        ).scalar_one_or_none()
        if recently_dismissed is not None:
            continue

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "timedelta\|dismissed_at\|recently_dismissed" /home/corby/jamm-os/app/api/concierge/cron.py
   Confirm all three present.
2. cd /home/corby/jamm-os/frontend
3. npm run build — zero TypeScript errors.
4. Restart backend.
5. In the test firm, dismiss both notifications. Refresh the page. Confirm neither re-fires immediately.