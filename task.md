STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Add assigned_to_name to TaskOut so the UI can display staff names

═══════════════════════════════════════════════════════════
CHANGE 1 — Add assigned_to_name to TaskOut schema
═══════════════════════════════════════════════════════════

FILE: app/schemas/task.py

Find:
class TaskOut(TaskBase):
    id: uuid.UUID
    client_id: uuid.UUID
    engagement_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

Change to:
class TaskOut(TaskBase):
    id: uuid.UUID
    client_id: uuid.UUID
    engagement_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    assigned_to_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

Make sure Optional is imported from typing.

═══════════════════════════════════════════════════════════
CHANGE 2 — Populate assigned_to_name in the task endpoints
═══════════════════════════════════════════════════════════

FILE: app/api/tasks.py (or wherever the task list and get endpoints are)

Find the list tasks endpoint and the get task endpoint. After fetching
tasks from the database, populate assigned_to_name by looking up the
user's full_name.

For the GET /tasks/ list endpoint, find where tasks are returned and
add a helper that enriches each task with the assignee name:

def enrich_task(task: Task, db: Session) -> TaskOut:
    out = TaskOut.model_validate(task)
    if task.assigned_to:
        from app.models.user import User
        user = db.get(User, task.assigned_to)
        if user:
            out.assigned_to_name = user.full_name
    return out

Then use this in both the list endpoint and the get single task endpoint
instead of returning the raw task object directly.

Check the existing code — if there's already a pattern for enriching
task responses, follow that pattern instead.

═══════════════════════════════════════════════════════════
CHANGE 3 — Display assigned_to_name in the frontend
═══════════════════════════════════════════════════════════

FILE: frontend/src/lib/api/tasks.ts (wherever mapTask is defined)

Find mapTask and add assigned_to_name mapping:

  assignedTo: raw.assigned_to ? String(raw.assigned_to) : null,
  assignedToName: raw.assigned_to_name ? String(raw.assigned_to_name) : null,

Also update the Task type to include assignedToName:
  assignedToName: string | null

FILE: frontend/src/app/tasks/[id]/page.tsx

Find:
  {task.assignedTo ?? '—'}

Change to:
  {task.assignedToName ?? task.assignedTo ?? '—'}

FILE: frontend/src/components/tasks/TaskTable.tsx or wherever the
task list table renders the Assigned To column.

Find where assignedTo is displayed in the task list and change to use
assignedToName with assignedTo as fallback.

After making all changes show:
1. Updated TaskOut schema
2. The enrich_task helper or equivalent
3. Updated mapTask function