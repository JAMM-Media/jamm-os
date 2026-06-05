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

TASK 4 OF 4: Block client portal users from concierge endpoint -- route.py

Pre-task:
VERIFY BEFORE ACT:
grep -n "get_current_firm\|get_current_user\|Depends\|import" /home/corby/jamm-os/app/api/concierge/route.py | head -20
Paste output before touching anything.

---

Change 1: Add user role check to concierge_chat endpoint

The concierge is for firm staff only. client_portal_user is a firm's client
and must never access the firm's internal assistant or context data.

First check if get_current_user and UserRole are already imported.
If not, add these imports at the top with the other app imports:

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.core.enums import UserRole

Then find:
@router.post("/chat")
def concierge_chat(
    body: ChatRequest,
    current_firm: Firm = Depends(get_current_firm),
):

Replace with:
@router.post("/chat")
def concierge_chat(
    body: ChatRequest,
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):

Then find the first line inside the function:
    if not current_firm.concierge_active:

Add this block immediately before it:
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

Apply the same pattern to the trigger-check, notifications, and
resolve endpoints -- all concierge endpoints must block portal users.

For each of these endpoints, add current_user: User = Depends(get_current_user)
to the signature and add the role check as the first line of the function body:

    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

Endpoints to update:
- POST /chat (done above)
- GET /clients/resolve
- POST /trigger-check
- GET /notifications
- PATCH /notifications/{notification_id}/read

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "client_portal_user\|UserRole" /home/corby/jamm-os/app/api/concierge/route.py
   Confirm client_portal_user appears 5 times -- once per endpoint.
2. python3 -c "from app.api.concierge.route import router; print('OK')"
   Must pass before stopping.
3. Restart the backend.

Final browser test:
- Log in as owner@riverside-demo.com -- normal firm staff login
- Open concierge, confirm it loads normally
- All previous tests from Task 3 still pass