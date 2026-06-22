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

# Task: Use real client name in Concierge drafts instead of [Client Name] placeholder

USE: claude sonnet

## VERIFY BEFORE ACT

```bash
sed -n '1185,1235p' /home/corby/jamm-os/app/api/concierge/prompts.py
```

Confirm entity_name is already injected into context_line when
entity_type == "client" and entity_name is known.

```bash
sed -n '1293,1302p' /home/corby/jamm-os/app/api/concierge/prompts.py
```

Confirm the CLIENT_EMAIL and IRS_RENEWAL rules currently say "Use [Client
Name] as placeholder" with no condition based on whether the name is known.

---

## WHAT IS WRONG

Confirmed via live testing: a CLIENT_EMAIL draft generated while viewing
Marcus & Diana Webb's own client page, with the agent's own preceding
message correctly saying "Here is what I have for Marcus & Diana Webb,"
still drafted the email body as "Hi [Client Name]," never substituting the
real name.

Root cause: the DRAFT RESPONSE PATTERNS section unconditionally instructs
the model to use [Client Name] as a literal placeholder for both
CLIENT_EMAIL and IRS_RENEWAL drafts, with no branch for the case where
entity_name is already known and injected into context. This is a real
instruction gap, not a model failure. The model did exactly what it was
told.

---

## ACTION

File: `/home/corby/jamm-os/app/api/concierge/prompts.py`

In the DRAFT RESPONSE PATTERNS section, update the CLIENT_EMAIL and
IRS_RENEWAL rules to read:

CLIENT_EMAIL: 2-4 sentences. Professional, warm tone. No em dashes. No

filler phrases. If you are viewing a specific client record and know the

client's real name from context, use their actual first name or full name

naturally in the greeting. Only use [Client Name] as a placeholder when no

specific client name is known from context. Keep it short enough to read

in 10 seconds.
IRS_RENEWAL: 2-3 sentences requesting updated authorization. Use the

client's real name if known from context, otherwise [Client Name].

Reference the specific form type (2848 or 8821) if known.


Do not change anything else in this section. Do not change INVOICE_ITEMS or
STAFF_REASSIGN rules. Do not touch any other file.

---

## VERIFY AFTER ACT

```bash
grep -n "use their actual first name\|use the client's real name" /home/corby/jamm-os/app/api/concierge/prompts.py
```

Expected: both new instructions present.

```bash
python3 -c "from app.api.concierge.route import router; print('OK')"
```

Expected: OK, no import errors.

---

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. While viewing a specific client's page (e.g. Marcus & Diana Webb), ask
   the Concierge to draft a follow-up email to this client.
3. Confirm the draft greeting uses the real client name, not [Client Name].
4. Regression check: from the Clients list (no specific client in context),
   ask a question that surfaces a CLIENT_EMAIL draft for one of several
   matching clients and confirm it correctly falls back to [Client Name]
   since no single client is in view.

Report what you observe at step 3 specifically.

---

## GIT

```bash
cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge CLIENT_EMAIL and IRS_RENEWAL drafts use the real client name when known from page context instead of always defaulting to [Client Name] placeholder"
git pull --rebase origin main
git push origin main
```

If conflicts on task.md use --theirs. Conflicts on source files use --ours.