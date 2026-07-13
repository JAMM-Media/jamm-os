# app/api/tasks.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.task import Task
from app.models.firm import Firm
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut, TaskStatus, BulkTaskUpdate
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import task as crud_task
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
from app.models.user import User
import app.services.task_service as task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


def enrich_task(task: Task, db: Session) -> TaskOut:
    out = TaskOut.model_validate(task)
    if task.assigned_to:
        user = db.get(User, task.assigned_to)
        if user:
            out.assigned_to_name = user.full_name
    return out


# ---------------------------------------------------------
# CREATE TASK
# manager_or_above can create tasks
# ---------------------------------------------------------
@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_manager_or_above),
):
    return task_service.create_task(
        db=db, payload=payload, firm_id=current_firm.id,
        current_user_id=current_user.id,
    )


# ---------------------------------------------------------
# LIST TASKS
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    client_id: UUID | None = None,
    engagement_id: UUID | None = None,
    status: TaskStatus | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    query = crud_task.get_tasks_for_firm(db, current_firm.id, client_id, engagement_id)

    if status:
        query = query.filter(Task.status == status.value)

    total = query.count()
    tasks = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [enrich_task(t, db) for t in tasks],
    }


# ---------------------------------------------------------
# BULK UPDATE TASKS
# ---------------------------------------------------------
@router.patch("/bulk")
def bulk_update_tasks(
    payload: BulkTaskUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return task_service.bulk_update_tasks(
        db=db, ids=payload.ids, update=payload.update, firm_id=current_firm.id,
    )


# ---------------------------------------------------------
# GET SINGLE TASK
# ---------------------------------------------------------
@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    task = crud_task.get_task_for_firm(db, task_id, current_firm.id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return enrich_task(task, db)


# ---------------------------------------------------------
# UPDATE TASK
# ---------------------------------------------------------
@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    result = task_service.update_task(
        db=db, task_id=task_id, payload=payload,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


# ---------------------------------------------------------
# DELETE TASK
# ---------------------------------------------------------
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_manager_or_above),
):
    result = task_service.delete_task(
        db=db, task_id=task_id,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")