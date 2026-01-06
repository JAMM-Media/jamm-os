# app/api/projects.py

from datetime import date
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, or_

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut

from pydantic import BaseModel
from app.models.task import Task
from app.schemas.task import TaskSummary
from app.schemas.client import ClientOut
from app.schemas.project import ProjectOverview  # if needed
from app.models.client import Client



router = APIRouter(prefix="/projects", tags=["projects"])




@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        client_id=payload.client_id,
        name=payload.name,
        description=payload.description,
        status=payload.status or "planning",
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/", response_model=List[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    client_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    start_before: Optional[date] = None,
    start_after: Optional[date] = None,
):
    """
    Basic filters:
    - ?client_id=<uuid>
    - ?status_filter=planning|active|completed
    - ?start_before=2025-01-01
    - ?start_after=2024-12-01
    """
    query = db.query(Project)

    if client_id:
        query = query.filter(Project.client_id == client_id)
    if status_filter:
        query = query.filter(Project.status == status_filter)
    if start_before:
        query = query.filter(Project.start_date <= start_before)
    if start_after:
        query = query.filter(Project.start_date >= start_after)

    # order by start_date, with nulls last
    query = query.order_by(Project.start_date.is_(None), Project.start_date)

    return query.all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/{project_id}/overview", response_model=ProjectOverview)
def get_project_overview(
    project_id: UUID,
    db: Session = Depends(get_db),
):
    project_stmt = select(Project).where(Project.id == project_id)
    project_result = db.execute(project_stmt)
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client = db.get(Client, project.client_id)

    tasks_stmt = select(Task).where(Task.project_id == project_id)
    tasks_result = db.execute(tasks_stmt)
    tasks = tasks_result.scalars().all()

    return ProjectOverview(
        project=project,
        client=client,
        tasks=tasks,
    )


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return None
