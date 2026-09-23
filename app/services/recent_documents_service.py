# app/services/recent_documents_service.py

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.recent_document_view import RecentDocumentView
from app.services.engagement_member_service import (
    FIRM_WIDE_MANAGEMENT_ROLES,
    is_member,
)

logger = logging.getLogger(__name__)


def _assert_can_read_engagement_recent_docs(
    db: Session,
    *,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    user,
) -> None:
    """Raise HTTP 404 if the user is not allowed to see this engagement's recent docs.

    Elevated roles (firm_owner, manager, system_admin) bypass the membership
    check, matching the same rule used by assert_can_access_document's
    engagement-scoped branch. All others must be a direct engagement member.

    Uses the real shared components from engagement_member_service rather than
    reimplementing the check inline:
      - FIRM_WIDE_MANAGEMENT_ROLES for the elevated bypass
      - is_member() for the direct membership lookup
    """
    if user.role in FIRM_WIDE_MANAGEMENT_ROLES:
        return
    if not is_member(db, firm_id=firm_id, engagement_id=engagement_id, user_id=user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")


def get_recent_documents(
    db: Session,
    *,
    firm_id: uuid.UUID,
    engagement_id: uuid.UUID,
    user,
    limit: int = 10,
) -> list:
    """Authorization-gated entry point for listing a user's recent documents.

    Checks engagement membership before querying, so the router stays thin
    (existence check + service call + response mapping only).
    Returns a list of (Document, last_viewed_at) tuples, most recent first.
    """
    _assert_can_read_engagement_recent_docs(
        db, firm_id=firm_id, engagement_id=engagement_id, user=user
    )
    return list_recent_documents(
        db, firm_id=firm_id, user_id=user.id, engagement_id=engagement_id, limit=limit
    )


def record_document_view(
    db: Session,
    *,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    engagement_id: uuid.UUID | None,
    document_id: uuid.UUID,
) -> None:
    """Upsert a recent-view row for this user+document pair.

    Only tracks engagement-scoped documents. Firm-library documents have no
    engagement_id (None), and Recent Documents was designed as an
    engagement-scoped feature. Attempting an insert with engagement_id=None
    violates the NOT NULL constraint on that column. Guard exits early so
    firm_library and Starter Templates downloads are silently skipped rather
    than turned into a constraint error.

    One row per (user_id, document_id). On conflict, only last_viewed_at
    and updated_at are refreshed -- created_at is never changed after the
    first insert, preserving the true first-view timestamp.

    Fire-and-forget safe: never raises. The except block always calls
    db.rollback() before logging so a failed insert can never leave the
    caller's session in a poisoned state.

    Uses the passed-in request session and commits inline, matching the
    audit_service pattern. A separate session is not needed because this is
    a synchronous fast-write within the same request, not a background task.
    """
    # Firm-library documents have no engagement_id; Recent Documents only
    # tracks engagement-scoped views.
    if engagement_id is None:
        return
    try:
        now = datetime.now(timezone.utc)
        stmt = pg_insert(RecentDocumentView).values(
            id=uuid.uuid4(),
            firm_id=firm_id,
            user_id=user_id,
            engagement_id=engagement_id,
            document_id=document_id,
            last_viewed_at=now,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_recent_view_user_document",
            set_={
                "last_viewed_at": now,
                "updated_at": now,
            },
        )
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to record document view for user=%s document=%s",
            user_id,
            document_id,
        )


def list_recent_documents(
    db: Session,
    *,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
    engagement_id: uuid.UUID,
    limit: int = 10,
) -> list:
    """Return the user's most recently viewed documents in this engagement.

    Excludes soft-deleted documents (deleted_at IS NOT NULL).
    Confirms each document still belongs to the correct firm and engagement
    as defense in depth against stale rows surviving some future cleanup gap.

    Returns a list of (Document, last_viewed_at) tuples, most recent first.
    """
    rows = (
        db.execute(
            select(Document, RecentDocumentView.last_viewed_at)
            .join(
                RecentDocumentView,
                RecentDocumentView.document_id == Document.id,
            )
            .where(
                RecentDocumentView.firm_id == firm_id,
                RecentDocumentView.user_id == user_id,
                RecentDocumentView.engagement_id == engagement_id,
                Document.firm_id == firm_id,
                Document.engagement_id == engagement_id,
                Document.deleted_at.is_(None),
            )
            .order_by(RecentDocumentView.last_viewed_at.desc())
            .limit(limit)
        )
        .all()
    )
    return [(doc, last_viewed_at) for doc, last_viewed_at in rows]
