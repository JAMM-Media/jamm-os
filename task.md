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

TASK 1 OF 3: Output filtering layer -- route.py

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before output filtering layer"

VERIFY BEFORE ACT:
grep -n "def generate\|assembled\|cleanContent\|stream" /home/corby/jamm-os/app/api/concierge/route.py
Paste output before touching anything.

---

Change 1: Add output filter function and apply it to streamed response

The output filter runs on the fully assembled response before it is
returned to the client. It checks for PII patterns and system prompt
leakage phrases and replaces them before the client ever sees them.

Find exactly:
    sanitized_messages = sanitize_messages(body.messages)

    def generate():
        with client.messages.stream(

Replace with:
    sanitized_messages = sanitize_messages(body.messages)

    import re

    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    EIN_PATTERN = re.compile(r'\b\d{2}-\d{7}\b')
    SYSTEM_PROMPT_LEAK_PHRASES = [
        "my instructions are",
        "my system prompt",
        "i was instructed to",
        "i am instructed to",
        "the system prompt says",
        "my prompt says",
        "i have been told to",
        "i have been configured",
        "as per my instructions",
        "according to my instructions",
    ]

    def filter_output(text: str) -> str:
        # Redact SSN patterns
        if SSN_PATTERN.search(text):
            logger.error(
                f"SECURITY: SSN pattern detected in output for firm {current_firm.id}"
            )
            text = SSN_PATTERN.sub("[REDACTED]", text)

        # Redact EIN patterns
        if EIN_PATTERN.search(text):
            logger.error(
                f"SECURITY: EIN pattern detected in output for firm {current_firm.id}"
            )
            text = EIN_PATTERN.sub("[REDACTED]", text)

        # Detect system prompt leakage attempts in output
        lower = text.lower()
        for phrase in SYSTEM_PROMPT_LEAK_PHRASES:
            if phrase in lower:
                logger.error(
                    f"SECURITY: Possible system prompt leakage in output "
                    f"for firm {current_firm.id}: phrase={phrase!r}"
                )
                return "I am JAMM Concierge. I am here to help you use JAMM PX."

        return text

    def generate():
        with client.messages.stream(

Now find the line inside generate() that yields the streamed chunks.
The full assembled response is not available during streaming -- the
filter must run on the complete assembled text before the final
setMessages call on the frontend.

Since this is a streaming endpoint, the output filter applies to each
complete chunk line, not the full response. Add the filter to each
data line before yielding:

Find exactly:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=get_system_prompt(autopilot_enabled=body.autopilot_enabled),
            messages=sanitized_messages,
        ) as stream:
            for text in stream.text_stream:
                data_lines = "\n".join(f"data: {line}" for line in text.split("\n"))
                yield f"{data_lines}\n\n"

Replace with:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=get_system_prompt(autopilot_enabled=body.autopilot_enabled),
            messages=sanitized_messages,
        ) as stream:
            assembled = ""
            for text in stream.text_stream:
                assembled += text
                data_lines = "\n".join(f"data: {line}" for line in text.split("\n"))
                yield f"{data_lines}\n\n"
            # Run output filter on fully assembled response
            filtered = filter_output(assembled)
            if filtered != assembled:
                # If filter changed the response, send a replacement sentinel
                yield f"data: \n\n"
                yield f"data: [FILTERED]\n\n"
                yield f"data: {filtered}\n\n"

Do not change anything else.

VERIFY AFTER ACT:
grep -n "filter_output\|SSN_PATTERN\|EIN_PATTERN\|SYSTEM_PROMPT_LEAK\|REDACTED\|assembled" /home/corby/jamm-os/app/api/concierge/route.py
Confirm all terms appear.
python3 -c "from app.api.concierge.route import router; print('OK')"
Must pass before stopping.