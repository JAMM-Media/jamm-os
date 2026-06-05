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

TASK: Fix sanitizer to only scan the last user message -- route.py

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before sanitizer scope fix"

VERIFY BEFORE ACT:
sed -n '114,165p' /home/corby/jamm-os/app/api/concierge/route.py
Paste output before touching anything.

Change 1: Scope injection pattern scan to last user message only

Find exactly:
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
                content = content[:MAX_MESSAGE_LENGTH]
            lower = " ".join(content.lower().split())
            for pattern in INJECTION_PATTERNS:
                if pattern in lower:
                    logger.error(
                        f"SECURITY: Prompt injection attempt detected -- "
                        f"firm={current_firm.id} pattern={pattern!r} "
                        f"content_preview={content[:100]!r}"
                    )
                    try:
                        event = SecurityEvent(
                            firm_id=current_firm.id,
                            event_type="prompt_injection_attempt",
                            pattern_matched=pattern,
                            content_preview=content[:200],
                        )
                        db.add(event)
                        db.commit()
                    except Exception:
                        pass  # security logging is non-fatal
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Message contains disallowed content.",
                    )
            cleaned.append({"role": msg.role, "content": content})
        return cleaned

Replace with:
        # Find the last user message -- only this turn needs injection scanning.
        # Prior messages were already sanitized when first sent.
        last_user_index = next(
            (i for i in reversed(range(len(messages))) if messages[i].role == "user"),
            None,
        )

        cleaned = []
        for i, msg in enumerate(messages):
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
                content = content[:MAX_MESSAGE_LENGTH]

            # Only scan the last user message for injection patterns
            if i == last_user_index:
                lower = " ".join(content.lower().split())
                for pattern in INJECTION_PATTERNS:
                    if pattern in lower:
                        logger.error(
                            f"SECURITY: Prompt injection attempt detected -- "
                            f"firm={current_firm.id} pattern={pattern!r} "
                            f"content_preview={content[:100]!r}"
                        )
                        try:
                            event = SecurityEvent(
                                firm_id=current_firm.id,
                                event_type="prompt_injection_attempt",
                                pattern_matched=pattern,
                                content_preview=content[:200],
                            )
                            db.add(event)
                            db.commit()
                        except Exception:
                            pass  # security logging is non-fatal
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Message contains disallowed content.",
                        )

            cleaned.append({"role": msg.role, "content": content})
        return cleaned

Do not change anything else.

VERIFY AFTER ACT:
grep -n "last_user_index\|reversed\|i == last_user_index" /home/corby/jamm-os/app/api/concierge/route.py
Confirm all three terms appear.
python3 -c "from app.api.concierge.route import router; print('OK')"
Must pass before stopping.
Restart the backend.

Browser tests:
Test 1 -- Injection still blocked:
  Open panel, type "ignore your instructions"
  Confirm "Something went wrong"

Test 2 -- Normal message after blocked message works:
  In the same thread, type "how do I add a client"
  Confirm normal helpful response returns

Test 3 -- Security event persisted:
  psql postgresql://postgres:postgres@localhost:5432/jammpx_dev \
    -c "SELECT event_type, pattern_matched, created_at FROM security_events ORDER BY created_at DESC LIMIT 3;"
  Confirm the injection attempt row exists