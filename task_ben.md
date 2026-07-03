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

# Task: Build the missing mark-as-read feature for Notes, with per-user read tracking

USE: claude sonnet

## VERIFY BEFORE ACT

cat /home/corby/jamm-os/app/models/note.py

Confirm the Note model has no is_read field and no existing read-tracking mechanism.

.venv/bin/alembic heads

Confirm the current single migration head before adding a new one.

## WHAT IS WRONG

Confirmed via live testing and full code tracing: the frontend (useNotes.ts) has always been correctly built to call POST /notes/mark-read and read an is_read field back from the API, but this backend feature was never actually implemented. The Note model has no is_read column, no separate read-tracking table exists, and no /notes/mark-read route is registered anywhere -- the notes router only has GET /, POST /, PATCH /{note_id}, and DELETE /{note_id}. Since FastAPI matches the incoming POST /notes/mark-read request against the PATCH and DELETE routes registered under the /{note_id} pattern (treating "mark-read" as a literal note_id value), and POST is not a valid method for either, the request correctly returns 405 Method Not Allowed. The frontend's markAsRead() call fails silently (empty .catch()), and every note reports isRead: false on every load regardless of what was previously "read," since nothing ever persists.

Read status must be tracked per-user, not globally on the note itself, since notes are visible to the whole firm team and one person reading a note should not mark it as read for everyone else -- this requires a separate join table, not a single boolean column on Note.

## ACTION

Step 1: New model. Create /home/corby/jamm-os/app/models/note_read.py:

# app/models/note_read.py
import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base_class import Base


class NoteRead(Base):
    __tablename__ = "note_reads"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("note_id", "user_id", name="uq_note_reads_note_user"),
    )

Add the import for this new model wherever app/models/__init__.py aggregates model imports, matching the existing pattern used for other models in that file, so Alembic autogenerate can see it.

Step 2: Generate and apply the migration.

cd /home/corby/jamm-os
.venv/bin/alembic revision --autogenerate -m "add note_reads table for per-user note read tracking"

Inspect the generated migration file to confirm it only creates the note_reads table with the correct columns, foreign keys, and unique constraint -- it should not include any unrelated changes. If it includes anything unexpected, stop and report rather than proceeding.

.venv/bin/alembic upgrade head

Confirm this applies cleanly with a single head.

Step 3: CRUD functions. In /home/corby/jamm-os/app/crud/note.py, add two new functions matching the existing file's style:

from app.models.note_read import NoteRead

def get_read_note_ids(
    db: Session,
    note_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> set[uuid.UUID]:
    if not note_ids:
        return set()
    stmt = select(NoteRead.note_id).where(
        NoteRead.note_id.in_(note_ids),
        NoteRead.user_id == user_id,
    )
    return set(db.execute(stmt).scalars().all())


def mark_notes_read(
    db: Session,
    note_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> None:
    if not note_ids:
        return
    already_read = get_read_note_ids(db, note_ids=note_ids, user_id=user_id)
    to_insert = [
        NoteRead(note_id=note_id, user_id=user_id)
        for note_id in note_ids
        if note_id not in already_read
    ]
    if to_insert:
        db.add_all(to_insert)
        db.commit()

Add the necessary import for NoteRead at the top of the file alongside the existing Note import.

Step 4: Schema. In /home/corby/jamm-os/app/schemas/note.py, add is_read to NoteOut and a new request schema for the mark-read endpoint:

Add to NoteOut (after is_deleted, before created_at, matching the existing field ordering style):

    is_read: bool = False

Add a new class near NoteCreate:

class NoteMarkReadRequest(BaseModel):
    entity_type: str
    entity_id: uuid.UUID

Step 5: Service layer. In /home/corby/jamm-os/app/services/note_service.py:

Modify get_notes to compute is_read per note for the requesting user. After fetching notes via crud_note.get_notes_for_entity, before building the result list, fetch the set of read note ids in one query and set is_read on each NoteOut:

def get_notes(
    db: Session,
    firm_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    requesting_user: User,
) -> list[NoteOut]:
    notes = crud_note.get_notes_for_entity(
        db,
        firm_id=firm_id,
        entity_type=entity_type,
        entity_id=entity_id,
        requesting_user_id=requesting_user.id,
    )
    note_ids = [note.id for note in notes]
    read_note_ids = crud_note.get_read_note_ids(db, note_ids=note_ids, user_id=requesting_user.id)
    result = []
    for note in notes:
        note_out = NoteOut.model_validate(note)
        note_out.is_read = note.id in read_note_ids
        _enrich(note_out, db)
        result.append(note_out)
    return result

Add a new service function for marking notes read, placed after get_notes:

def mark_notes_read(
    db: Session,
    firm_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    requesting_user: User,
) -> None:
    notes = crud_note.get_notes_for_entity(
        db,
        firm_id=firm_id,
        entity_type=entity_type,
        entity_id=entity_id,
        requesting_user_id=requesting_user.id,
    )
    note_ids = [note.id for note in notes]
    crud_note.mark_notes_read(db, note_ids=note_ids, user_id=requesting_user.id)

Step 6: Route. In /home/corby/jamm-os/app/api/notes.py, add the missing endpoint. Update the import line to include NoteMarkReadRequest, and add the new route before the existing /{note_id} routes (route ordering matters in FastAPI -- a literal path segment like /mark-read must be registered before a parameterized /{note_id} pattern, or the parameterized route will incorrectly match it first, which is the exact bug being fixed):

Change the import line:

from app.schemas.note import NoteCreate, NoteUpdate, NoteOut, NoteMarkReadRequest

Add this new route immediately after create_note (POST /) and before update_note (PATCH /{note_id}):

@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notes_read(
    data: NoteMarkReadRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    note_service.mark_notes_read(
        db,
        firm_id=current_firm.id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        requesting_user=current_user,
    )

Do not change any other existing route in this file. Do not change the frontend -- useNotes.ts is already correctly built for this feature and requires no changes.

## VERIFY AFTER ACT

grep -n "class NoteRead" /home/corby/jamm-os/app/models/note_read.py

Expected: present.

.venv/bin/alembic heads

Expected: single head, the new migration applied.

grep -n "is_read" /home/corby/jamm-os/app/schemas/note.py /home/corby/jamm-os/app/services/note_service.py

Expected: present in both, with the correct per-user computation logic in note_service.py.

grep -n "@router.post(\"/mark-read\"" /home/corby/jamm-os/app/api/notes.py

Expected: present, positioned before the /{note_id} routes.

python3 -c "from app.main import app; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend.
2. Open a client's Notes panel, confirm existing notes show as unread (if any exist) or add a new note first.
3. Trigger the mark-as-read action (whatever UI action calls markAsRead() -- likely opening the panel itself, based on the existing hook).
4. Check DevTools Network tab, confirm POST /notes/mark-read now returns 204, not 405.
5. Reload the page and reopen the same client's Notes panel. Confirm the previously-read notes now correctly show as read (is_read: true from the API), not reverting to unread.
6. Regression check: create a new note as a different concept -- confirm it correctly shows as unread until read, and that read status is genuinely per-user (if testing with two different staff accounts, one marking notes read should not affect the other's unread count, though this may not be practically testable without a second account and can be reported as "not tested" if only one account is available).

Report what you observe at steps 4 and 5 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: implement the missing mark-as-read feature for Notes, which the frontend was always correctly built for but had no backend support. Added a note_reads join table for per-user read tracking (since notes are shared across the firm team and one person's read status should not affect others), the missing POST /notes/mark-read endpoint, and per-user is_read computation on note retrieval. This also fixes the underlying 405 error, which was caused by the request incorrectly matching the /{note_id} pattern since no literal /mark-read route existed"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.