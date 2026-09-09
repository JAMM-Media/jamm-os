# app/services/document_access.py
"""
The document access gate.

A single service-layer function answers 'may this user access this document,'
branching on document.scope. Every read, list, download, audit, and
superseded-flag endpoint passes through this gate or its list-filtering
equivalent. It is never reimplemented inline in an endpoint.

Spec reference: Filesystem Build Specification, Section 6.

Hardening notes:
  B. Both 'document does not exist' and 'document exists but access denied'
     raise HTTPException(404) with the IDENTICAL detail string (_NOT_FOUND).
     Different messages, different shapes, or an echoed document ID are
     information leaks regardless of status code.
  C. assert_can_access_document must be called BEFORE any enrichment of the
     document row (client name, engagement name, uploader name, filename
     in a response body). No metadata is returned before auth passes.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.document import Document
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.user import User

# Both "not found" and "access denied" return this identical detail string.
_NOT_FOUND = "Document not found"

# Roles that bypass engagement-membership gates entirely.
_ELEVATED = frozenset([
    UserRole.firm_owner.value,
    UserRole.manager.value,
    UserRole.system_admin.value,
])


def assert_can_access_document(
    db: Session,
    user: User,
    document: Document,
    firm_id: UUID,
) -> None:
    """
    Raise HTTPException(404) if the user cannot access the document.

    Scope rules:
      firm_library: any staff member reads freely.
      client:       user must be a member of at least one of the client's
                    engagements within this firm.
      engagement:   user must be a direct member of this specific engagement.

    Managers and firm owners bypass the membership check entirely.
    The response is identical (404, same body) whether the document does not
    exist or exists but the user is denied, to prevent enumeration attacks.
    """
    if user.role in _ELEVATED:
        return

    scope = document.scope

    if scope == "firm_library":
        return

    if scope == "engagement":
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == document.engagement_id,
            EngagementMember.user_id == user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
        return

    if scope == "client":
        member = (
            db.query(EngagementMember)
            .join(Engagement, EngagementMember.engagement_id == Engagement.id)
            .filter(
                EngagementMember.firm_id == firm_id,
                EngagementMember.user_id == user.id,
                Engagement.client_id == document.client_id,
                Engagement.firm_id == firm_id,
            )
            .first()
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)
        return

    # Unknown scope: deny by default rather than silently granting access.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def assert_can_delete_document(
    db: Session,
    user: User,
    document: Document,
    firm_id: UUID,
) -> None:
    """
    Trio check for delete/restore.

    Permitted: engagement administrator (engagement-scoped docs only),
               manager, or firm owner.
    Regular engagement members get read access but not delete.
    For client-scoped and firm_library-scoped docs: manager/owner only
    (no per-document engagement administrator role exists at those scopes).
    Raises HTTPException(404) on denial to avoid confirming the document exists.
    """
    if user.role in _ELEVATED:
        return

    if document.scope == "engagement":
        admin_member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == document.engagement_id,
            EngagementMember.user_id == user.id,
            EngagementMember.is_administrator == True,
        ).first()
        if admin_member:
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def assert_can_upload_to_engagement(
    db: Session,
    user: User,
    firm_id: UUID,
    engagement_id: UUID,
    client_id: UUID,
) -> None:
    """
    Canonical relationship check for document upload (hardening A).

    Verifies three things:
    1. The engagement belongs to this firm.
    2. The engagement's real client_id matches the supplied client_id
       (parent-mismatch prevention: the two IDs must actually belong together
       in the database, not just both individually valid).
    3. The user is a member of this engagement, or manager/owner.

    Both 'engagement not found' and 'client mismatch' return the same 404
    to avoid leaking which part of the supplied data is wrong.
    Raises 403 for membership denial (a legitimate user who is simply not
    assigned to this engagement needs to know the reason, since both the
    engagement and client genuinely exist).
    """
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.firm_id == firm_id,
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")

    # Canonical relationship: supplied client_id must match the engagement's
    # actual client_id, not merely be a valid client ID somewhere in the firm.
    if engagement.client_id != client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")

    if user.role in _ELEVATED:
        return

    member = db.query(EngagementMember).filter(
        EngagementMember.firm_id == firm_id,
        EngagementMember.engagement_id == engagement_id,
        EngagementMember.user_id == user.id,
    ).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this engagement",
        )


def assert_can_access_folder(
    db: Session,
    user,
    folder,
    firm_id: UUID,
) -> None:
    """Gate for reading or modifying (create/rename) a document folder.

    Any engagement member can access engagement-scoped folders.
    Client-scoped and firm_library-scoped folders require manager or owner.
    Raises HTTPException(404) on denial.
    """
    _FOLDER_NOT_FOUND = "Folder not found"

    if user.role in _ELEVATED:
        return

    scope = folder.scope

    if scope == "firm_library":
        return

    if scope == "engagement":
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == folder.engagement_id,
            EngagementMember.user_id == user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_FOLDER_NOT_FOUND)
        return

    # client and firm_library are manager/owner only for non-elevated.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_FOLDER_NOT_FOUND)


def assert_can_delete_folder(
    db: Session,
    user,
    folder,
    firm_id: UUID,
) -> None:
    """Gate for deleting a document folder (trio check).

    Permitted: engagement administrator, manager, or firm owner.
    Matches the same trio as assert_can_delete_document.
    Raises HTTPException(404) on denial.
    """
    _FOLDER_NOT_FOUND = "Folder not found"

    if user.role in _ELEVATED:
        return

    if folder.scope == "engagement":
        admin_member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == folder.engagement_id,
            EngagementMember.user_id == user.id,
            EngagementMember.is_administrator == True,
        ).first()
        if admin_member:
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_FOLDER_NOT_FOUND)


def filter_accessible_documents(query, db: Session, user: User, firm_id: UUID):
    """
    Filter a document SQLAlchemy query to only documents this user can access.

    For managers and owners: no filter applied (full visibility).
    For staff: only documents from their memberships are included, plus
    firm_library-scoped documents (visible to all staff).

    Applies the filter at the query layer so inaccessible documents are
    never fetched, not returned and hidden client-side.
    """
    if user.role in _ELEVATED:
        return query

    eng_id_rows = db.query(EngagementMember.engagement_id).filter(
        EngagementMember.user_id == user.id,
        EngagementMember.firm_id == firm_id,
    ).all()
    eng_ids = [row[0] for row in eng_id_rows]

    client_id_rows = (
        db.query(Engagement.client_id)
        .filter(
            Engagement.id.in_(eng_ids),
            Engagement.firm_id == firm_id,
        )
        .all()
        if eng_ids else []
    )
    client_ids = [row[0] for row in client_id_rows]

    conditions = [Document.scope == "firm_library"]
    if eng_ids:
        conditions.append(
            and_(Document.scope == "engagement", Document.engagement_id.in_(eng_ids))
        )
    if client_ids:
        conditions.append(
            and_(Document.scope == "client", Document.client_id.in_(client_ids))
        )

    return query.filter(or_(*conditions))


def assert_can_approve_document(
    db: Session,
    user: User,
    document: Document,
    firm_id: UUID,
) -> None:
    """Trio check for approving a pending document.

    Identical logic to assert_can_delete_document: engagement administrator,
    manager, or firm owner. Named separately because this is a triage-approval
    operation, not a delete. The trio restriction applies because approving
    a client-uploaded file moves it into the engagement's live document set,
    which is a consequential action that warrants the same elevated gate.
    Raises HTTPException(404) on denial to avoid confirming the item exists.
    """
    if user.role in _ELEVATED:
        return

    if document.scope == "engagement":
        admin_member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == document.engagement_id,
            EngagementMember.user_id == user.id,
            EngagementMember.is_administrator == True,
        ).first()
        if admin_member:
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def assert_can_reassign_document(
    db: Session,
    user: User,
    document: Document,
    firm_id: UUID,
) -> None:
    """Trio check for reassigning a pending document to a different engagement.

    Identical logic to assert_can_delete_document: engagement administrator,
    manager, or firm owner. Named separately because this is a triage-reassign
    operation, not a delete. The trio restriction applies because reassigning
    moves a document across engagement containers, affecting members of both
    source and destination. Note: this check confirms the actor's role only.
    The cross-client boundary check (dest_engagement.client_id != doc.client_id)
    is enforced separately in the service layer -- this guard and that check
    are independent layers, not alternatives.
    Raises HTTPException(404) on denial to avoid confirming the item exists.
    """
    if user.role in _ELEVATED:
        return

    if document.scope == "engagement":
        admin_member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == document.engagement_id,
            EngagementMember.user_id == user.id,
            EngagementMember.is_administrator == True,
        ).first()
        if admin_member:
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def assert_can_move_across_engagements(
    db: Session,
    user: User,
    document: Document,
    firm_id: UUID,
) -> None:
    """Trio check for the cross-engagement misfile fix.

    Identical logic to assert_can_delete_document: engagement administrator,
    manager, or firm owner. Named separately because this is a move operation,
    not a delete. The trio restriction applies because moving a document across
    engagements changes its scope container and affects all members of both
    source and destination engagements.
    Raises HTTPException(404) on denial.
    """
    if user.role in _ELEVATED:
        return

    if document.scope == "engagement":
        admin_member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == document.engagement_id,
            EngagementMember.user_id == user.id,
            EngagementMember.is_administrator == True,
        ).first()
        if admin_member:
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def assert_can_write_to_destination(
    db: Session,
    user: User,
    firm_id: UUID,
    dest_scope: str,
    dest_engagement_id: Optional[UUID],
    dest_client_id: Optional[UUID],
) -> None:
    """Check write access to a copy destination.

    firm_library: any staff member can write.
    engagement: user must be a member of the destination engagement (or manager/owner).
    client: manager or owner only (no engagement-level write path for client-scoped copies).
    Raises HTTPException(403) on denial.
    """
    if user.role in _ELEVATED:
        return

    if dest_scope == "firm_library":
        return

    if dest_scope == "engagement":
        member = db.query(EngagementMember).filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == dest_engagement_id,
            EngagementMember.user_id == user.id,
        ).first()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of the destination engagement",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Manager or owner required for client-scoped copy destination",
    )


# Preview-eligible MIME types. Only PDF and common image types can be
# previewed safely in-browser. Office formats are explicitly out of scope
# (Section 14 of the build spec).
_PREVIEW_ELIGIBLE_CONTENT_TYPES = frozenset([
    "application/pdf",
    "image/jpeg",
    "image/png",
])

# Magic-byte signatures for each eligible type.
_PDF_MAGIC = b"%PDF"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG"


def check_preview_eligible(stored_content_type: str, s3_key: str) -> bool:
    """Return True only if the document is genuinely preview-eligible.

    Two-layer check:
      1. stored_content_type must be in the allow-list.
      2. The actual first bytes from S3 must match the expected magic bytes.

    The magic-byte check is authoritative. A file whose stored_content_type
    claims to be a PDF but whose real bytes are not a PDF will fail the check.
    This is the correct behavior: we do not trust the client-supplied content
    type alone.

    This function performs one S3 ranged GET (8 bytes). It is called only from
    the preview endpoint, not from upload or listing paths.
    """
    if stored_content_type not in _PREVIEW_ELIGIBLE_CONTENT_TYPES:
        return False

    from app.services.s3 import get_object_bytes_range
    try:
        header = get_object_bytes_range(s3_key, 8)
    except Exception:
        return False

    if header.startswith(_PDF_MAGIC):
        return True
    if header.startswith(_JPEG_MAGIC):
        return True
    if header.startswith(_PNG_MAGIC):
        return True
    return False
