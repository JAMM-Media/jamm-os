# app/services/task_file_link_service.py

"""
Service layer for task-to-document links (filesystem spec Section 13).

Every read and write goes through the Phase 2 access gate
(assert_can_access_document / filter_accessible_documents). Task visibility
(require_staff_or_above) is necessary but not sufficient: a staff member
who can open a task is not guaranteed to be a member of that task's
engagement, and only engagement members may see or modify the linked files.

Only CLIENT-type tasks are eligible. INTERNAL tasks have no engagement_id
and therefore cannot link files; the service refuses them with 404 to avoid
leaking whether the task exists under a different type.

Unlinking requires the same access check as linking (assert_can_access_document).
A staff member who cannot access a document should not be able to silently
remove its link from a task. Symmetry also prevents information leakage:
a denied user should see a 404, not a 204 that reveals the link existed.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.task import Task
from app.models.task_file_link import TaskFileLink
from app.models.user import User
from app.schemas.document import DocumentOut
from app.schemas.task_file_link import TaskFileLinkOut
from app.services.document_access import assert_can_access_document, filter_accessible_documents


def _doc_to_link_out(doc: Document, link_id, link_created_at) -> TaskFileLinkOut:
    """Build a TaskFileLinkOut safely.

    model_validate(doc) alone would fail because link_id and link_created_at
    are required fields that the ORM object does not carry. Validate to
    DocumentOut first (which understands from_attributes), dump to a dict,
    then construct TaskFileLinkOut with the link fields added.
    """
    doc_dict = DocumentOut.model_validate(doc).model_dump()
    return TaskFileLinkOut(**doc_dict, link_id=link_id, link_created_at=link_created_at)


def _load_client_task(db: Session, firm_id: UUID, task_id: UUID) -> Task:
    """Return a CLIENT-type task or raise 404.

    Conflating 'not found' with 'wrong type' is intentional: the file-link
    sub-resource does not exist for INTERNAL tasks, so the semantics of 404
    are correct and the response leaks nothing about the underlying task type.
    """
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.firm_id == firm_id,
    ).first()
    if not task or task.task_type != "client":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _load_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def link_file_to_task(
    db: Session,
    firm_id: UUID,
    task_id: UUID,
    document_id: UUID,
    current_user_id: UUID,
) -> TaskFileLink:
    """
    Link a document to a task. Idempotent: returns the existing row if the
    link already exists rather than raising an error.

    Raises 404 if the task is not found or is INTERNAL-type.
    Raises 404 if the document is not found or the Phase 2 gate denies access.
    Raises 422 if the document is not in the task's engagement.
    """
    task = _load_client_task(db, firm_id, task_id)
    user = _load_user(db, current_user_id)

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.firm_id == firm_id,
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Phase 2 gate: raises 404 if the user cannot access this document.
    assert_can_access_document(db, user, document, firm_id)

    # Engagement scope: the document must belong to the task's engagement.
    # firm_library documents (engagement_id=None) do not belong to any
    # engagement and are therefore excluded.
    if document.engagement_id != task.engagement_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document does not belong to this task's engagement.",
        )

    existing = db.query(TaskFileLink).filter(
        TaskFileLink.task_id == task_id,
        TaskFileLink.document_id == document_id,
    ).first()
    if existing:
        return existing

    link = TaskFileLink(
        firm_id=firm_id,
        task_id=task_id,
        document_id=document_id,
        created_by=current_user_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_task_file_links(
    db: Session,
    firm_id: UUID,
    task_id: UUID,
    current_user_id: UUID,
) -> list[TaskFileLinkOut]:
    """
    Return all linked documents the current user can access.

    filter_accessible_documents silently excludes documents the user cannot
    see (matching the spec's filter-not-refuse semantics from Section 6).
    Soft-deleted documents are included with deleted_at populated, not excluded
    (spec: a trashed file remains visible with a label).
    """
    _load_client_task(db, firm_id, task_id)
    user = _load_user(db, current_user_id)

    rows_query = (
        db.query(
            Document,
            TaskFileLink.id.label("link_id"),
            TaskFileLink.created_at.label("link_created_at"),
        )
        .join(TaskFileLink, TaskFileLink.document_id == Document.id)
        .filter(
            TaskFileLink.firm_id == firm_id,
            TaskFileLink.task_id == task_id,
            Document.firm_id == firm_id,
        )
    )
    # Phase 2 gate applied at the query layer.
    rows_query = filter_accessible_documents(rows_query, db, user, firm_id)
    rows = rows_query.all()

    results: list[TaskFileLinkOut] = []
    for row in rows:
        doc = row[0]
        link_id = row[1]
        link_created_at = row[2]
        results.append(_doc_to_link_out(doc, link_id, link_created_at))
    return results


def unlink_file_from_task(
    db: Session,
    firm_id: UUID,
    task_id: UUID,
    document_id: UUID,
    current_user_id: UUID,
) -> None:
    """
    Remove the link row. Requires the same Phase 2 access check as linking.

    Symmetry reasoning: a user who cannot access a document should not be
    able to unlink it (they should not know the link exists). A 404 on the
    document check is identical in shape to what the list endpoint would
    have shown them (an empty list), so no capability is revealed.
    """
    _load_client_task(db, firm_id, task_id)
    user = _load_user(db, current_user_id)

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.firm_id == firm_id,
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    assert_can_access_document(db, user, document, firm_id)

    link = db.query(TaskFileLink).filter(
        TaskFileLink.task_id == task_id,
        TaskFileLink.document_id == document_id,
        TaskFileLink.firm_id == firm_id,
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File link not found")

    db.delete(link)
    db.commit()
