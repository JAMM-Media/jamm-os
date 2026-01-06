# app/api/tasks.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional


from app.db.session import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# -----------------------
# GET /tasks/
# -----------------------
@router.get("/", response_model=List[TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    client_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    status: Optional[str] = None,
):
    stmt = select(Task)

    if client_id:
        stmt = stmt.where(Task.client_id == client_id)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    if status:
        stmt = stmt.where(Task.status == status)

    stmt = stmt.order_by(Task.due_date)

    result = db.execute(stmt)
    return result.scalars().all()

# -----------------------
# GET /tasks/{id}
# -----------------------
@router.get("/{id}", response_model=TaskOut)
def get_task(id: UUID, db: Session = Depends(get_db)):
    task = db.query(Task).get(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# -----------------------
# POST /tasks/
# -----------------------
@router.post("/", response_model=TaskOut)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**task_in.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# -----------------------
# PATCH /tasks/{id}
# -----------------------
@router.patch("/{id}", response_model=TaskOut)
def update_task(id: UUID, task_in: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).get(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


# -----------------------
# DELETE /tasks/{id}
# -----------------------
@router.delete("/{id}")
def delete_task(id: UUID, db: Session = Depends(get_db)):
    task = db.query(Task).get(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}
