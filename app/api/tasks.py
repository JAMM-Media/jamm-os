# app/api/tasks.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut

router = APIRouter()


@router.post("/tasks/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    db_task = Task(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.get("/tasks/", response_model=list[TaskOut])
def list_tasks(client_id: UUID | None = None, project_id: UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(Task)
    if client_id:
        query = query.filter(Task.client_id == client_id)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    return query.all()


@router.get("/tasks/{id}", response_model=TaskOut)
def get_task(id: UUID, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/tasks/{id}", response_model=TaskOut)
def update_task(id: UUID, task_update: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in task_update.dict(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(id: UUID, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
