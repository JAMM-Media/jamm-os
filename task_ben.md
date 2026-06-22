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

# Task: Fix UserOut missing firm_type and concierge_active, sourced from Firm not User

USE: claude sonnet

## VERIFY BEFORE ACT

cat /home/corby/jamm-os/app/schemas/user.py

Confirm the exact current shape of UserOut and UserBase before adding fields.

grep -n "def read_users_me" -A 10 /home/corby/jamm-os/app/api/users.py

Confirm the current handler just returns current_user directly with no firm join.

## WHAT IS WRONG

Confirmed via live testing and direct DB query: a firm with firm_type already
set to 'tax_and_bookkeeping' in the database still triggered the
pre-onboarding "what does your firm do most" gate in the Concierge panel on
every single session, regardless of firm state.

Root cause: AuthUser.firm_type and AuthUser.concierge_active on the frontend
are read from whatever /users/me returns, serialized through UserOut.
UserOut is built from_attributes directly off the User model only.
firm_type and concierge_active are columns on the Firm model, not User, so
they were never present on the User row UserOut maps from. The API was
returning a user object where these fields are structurally always null,
independent of the real firm_type or concierge_active values in the
database. Every onboarding-state check on the frontend that reads
user?.firm_type, including the Concierge panel's first-message gate, has
been operating on missing data this entire time.

## ACTION

File: /home/corby/jamm-os/app/schemas/user.py

Add firm_type: Optional[str] = None and concierge_active: bool = False as
fields on UserOut (not UserBase, since these are firm-level, not intrinsic
to the user identity itself).

File: /home/corby/jamm-os/app/api/users.py

Update read_users_me to also load the current user's Firm and attach
firm_type and concierge_active onto the response before returning. Use the
existing get_current_firm dependency already used in get_my_firm a few
lines below in this same file, add it as a dependency to read_users_me, and
build the response explicitly:

def read_users_me(
    current_user: User = Depends(get_current_user),
    current_firm: Firm = Depends(get_current_firm),
):
    user_out = UserOut.model_validate(current_user)
    user_out.firm_type = current_firm.firm_type
    user_out.concierge_active = current_firm.concierge_active
    return user_out

Adjust import statements as needed for Firm and get_current_firm if not
already imported in this file. Do not change get_my_firm or any other route
in this file. Do not touch the Next.js proxy route, it already passes
through whatever the backend returns correctly.

## VERIFY AFTER ACT

grep -n "firm_type\|concierge_active" /home/corby/jamm-os/app/schemas/user.py

Expected: both fields present on UserOut.

python3 -c "from app.api.users import router; print('OK')"

Expected: OK, no import errors.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart both backend and frontend.
2. Log in as a user belonging to Riverside Tax & Advisory (firm_type already
   set to tax_and_bookkeeping in the database).
3. Open the Concierge panel from a fresh session (clear sessionStorage or
   use a private browser window so jamm_concierge_messages does not mask
   this test).
4. Confirm the panel does NOT show the "what does your firm do most" gate
   message. It should go straight to the __OPEN__ flow instead.
5. Regression check: create or use a test firm where firm_type is genuinely
   null in the database, confirm that firm still correctly sees the
   onboarding gate message. This confirms the fix reads real data rather
   than always suppressing the gate.

Report what you observe at step 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: UserOut now includes firm_type and concierge_active sourced from the Firm row, not the User row, fixing the Concierge onboarding gate firing for every firm regardless of actual firm_type state"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.