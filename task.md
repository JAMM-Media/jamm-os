STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix team invite 422 — make firm_id optional in UserCreate schema

FILE TO EDIT: app/schemas/user.py

PROBLEM: UserCreate requires firm_id as a mandatory field. The frontend
doesn't send firm_id (correctly — the backend injects it from JWT).
Pydantic rejects the request with a 422 before the endpoint runs.

The backend endpoint already does:
  user_in_with_firm = user_in.model_copy(update={"firm_id": current_firm.id})

So firm_id in the request body is always overridden anyway.

FIX: Make firm_id optional with a default of None in UserCreate:

Find:
class UserCreate(UserBase):
    password: str
    # firm_id is required when creating a user — every user must belong to a firm.
    firm_id: UUID

Change to:
class UserCreate(UserBase):
    password: str
    # firm_id is injected from JWT in the endpoint — optional in the request body
    firm_id: Optional[UUID] = None

Also make sure Optional is imported from typing — it already is in
this file so no import change needed.

After making the change show the updated UserCreate class.