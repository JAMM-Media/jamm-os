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

TASK 1 OF 2: Backend security hardening -- route.py

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before backend security hardening"

VERIFY BEFORE ACT:
sed -n '35,42p' /home/corby/jamm-os/app/api/concierge/route.py
sed -n '79,105p' /home/corby/jamm-os/app/api/concierge/route.py
Paste both before touching anything.

---

Change 1: Lock message role to user or assistant only

Find exactly:
class MessageItem(BaseModel):
    role: str
    content: str

Replace with:
class MessageItem(BaseModel):
    role: str
    content: str

    def validate_role(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(f"Invalid message role: {self.role!r}")

Then inside sanitize_messages, add role validation at the start of the
for loop, immediately before the content length check:

Find exactly:
        cleaned = []
        for msg in messages:
            content = msg.content
            if len(content) > MAX_MESSAGE_LENGTH:

Replace with:
        cleaned = []
        for msg in messages:
            if msg.role not in ("user", "assistant"):
                logger.warning(
                    f"Invalid message role for firm {current_firm.id}: {msg.role!r}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Message contains disallowed content.",
                )
            content = msg.content
            if len(content) > MAX_MESSAGE_LENGTH:

---

Change 2: Normalize whitespace before injection pattern matching

Find exactly:
            lower = content.lower()
            for pattern in INJECTION_PATTERNS:
                if pattern in lower:

Replace with:
            lower = " ".join(content.lower().split())
            for pattern in INJECTION_PATTERNS:
                if pattern in lower:

This collapses all whitespace variants -- double spaces, tabs, newlines --
into single spaces before matching. Bypasses using extra whitespace are blocked.

---

Change 3: Add per-firm rate limit on /chat endpoint

VERIFY BEFORE ACT:
grep -n "limiter\|rate_limit\|slowapi\|from app.core" /home/corby/jamm-os/app/api/concierge/route.py
Paste output.

If limiter is not already imported, check how it is imported in other route files:
grep -rn "limiter" /home/corby/jamm-os/app/api/ | grep "import" | head -5
Paste output then add the correct import.

Then find:
@router.post("/chat")
def concierge_chat(

Replace with:
@router.post("/chat")
@limiter.limit("60/minute")
def concierge_chat(
    request: Request,

Add Request to the existing FastAPI imports at the top of the file if not present:
from fastapi import APIRouter, Depends, HTTPException, Request, status

---

Change 4: Escalate repeated injection attempts

Inside sanitize_messages, find exactly:
                    logger.warning(
                        f"Potential prompt injection detected for firm "
                        f"{current_firm.id}: pattern={pattern!r}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Message contains disallowed content.",
                    )

Replace with:
                    logger.error(
                        f"SECURITY: Prompt injection attempt detected -- "
                        f"firm={current_firm.id} pattern={pattern!r} "
                        f"content_preview={content[:100]!r}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Message contains disallowed content.",
                    )

Changing logger.warning to logger.error ensures injection attempts surface
at a higher severity level in any log monitoring setup.

---

VERIFY AFTER ACT:
1. grep -n "user.*assistant\|role not in\|split()\|logger.error\|SECURITY:" /home/corby/jamm-os/app/api/concierge/route.py
   Confirm all four changes appear.
2. python3 -c "from app.api.concierge.route import router; print('OK')"
   Must pass before stopping.
3. Restart the backend.