# app/services/import_batch_service.py

"""
Import batch service -- Phase 2: draft creation and confirmation.

No S3 interaction. No file bytes move here. This phase creates and validates
the database records describing what will be imported.
"""

import posixpath
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.models.import_item import ImportItem
from app.models.user import User
from app.schemas.import_batch import ImportBatchCreate
from app.services.document_access import assert_can_bulk_import


def _normalize_path(raw: str) -> str:
    """Sanitize a browser-supplied relative path (e.g. webkitRelativePath).

    Strips null bytes and backslashes, resolves separators, removes any
    path traversal components (..), and returns the cleaned path. The filename
    is always the last component; if normalization produces an empty string the
    raw filename is used as a fallback.
    """
    cleaned = raw.replace("\x00", "").replace("\\", "/")
    parts = posixpath.normpath(cleaned).split("/")
    safe = [p for p in parts if p and p != "." and p != ".."]
    return "/".join(safe) if safe else raw.split("/")[-1]


def _validate_scope_fks(
    scope: str,
    client_id: Optional[UUID],
    engagement_id: Optional[UUID],
) -> None:
    """Enforce scope/FK consistency in application code before hitting the DB
    CHECK constraint, so the 422 message is actionable rather than cryptic."""
    if scope == "engagement":
        if not client_id or not engagement_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="engagement scope requires both client_id and engagement_id",
            )
    elif scope == "client":
        if not client_id or engagement_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="client scope requires client_id and no engagement_id",
            )
    elif scope == "firm_library":
        if client_id or engagement_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="firm_library scope requires neither client_id nor engagement_id",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid scope '{scope}'; must be engagement, client, or firm_library",
        )


def _validate_destination_folder(
    db: Session,
    destination_folder_id: UUID,
    firm_id: UUID,
    scope: str,
    engagement_id: Optional[UUID],
) -> None:
    """Confirm the destination folder exists, belongs to this firm, is not
    soft-deleted, and matches the batch's own scope and engagement."""
    from app.crud.document_folder import get_document_folder
    from app.models.document_folder import DocumentFolder

    folder = get_document_folder(db, folder_id=destination_folder_id, firm_id=firm_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Destination folder not found",
        )
    if folder.scope != scope:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Destination folder scope '{folder.scope}' does not match batch scope '{scope}'",
        )
    if scope == "engagement" and folder.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Destination folder belongs to a different engagement",
        )


def create_draft(
    *,
    db: Session,
    firm_id: UUID,
    user: User,
    payload: ImportBatchCreate,
) -> tuple[ImportBatch, list[ImportItem]]:
    """Create an import batch in draft status with all planned items.

    Empty items lists are refused at creation: the browser must enumerate
    at least one file before submitting. Refusing here rather than at confirm
    prevents unactionable draft records from cluttering the database.
    """
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A batch must contain at least one item",
        )

    _validate_scope_fks(payload.scope, payload.client_id, payload.engagement_id)

    assert_can_bulk_import(
        db=db,
        user=user,
        scope=payload.scope,
        engagement_id=payload.engagement_id,
        firm_id=firm_id,
    )

    if payload.destination_folder_id is not None:
        _validate_destination_folder(
            db=db,
            destination_folder_id=payload.destination_folder_id,
            firm_id=firm_id,
            scope=payload.scope,
            engagement_id=payload.engagement_id,
        )

    total_bytes = sum(item.expected_bytes for item in payload.items)

    batch = ImportBatch(
        firm_id=firm_id,
        created_by_user_id=user.id,
        scope=payload.scope,
        client_id=payload.client_id,
        engagement_id=payload.engagement_id,
        destination_folder_id=payload.destination_folder_id,
        conflict_policy=payload.conflict_policy.value,
        total_files=len(payload.items),
        total_bytes=total_bytes,
    )
    db.add(batch)
    db.flush()

    items: list[ImportItem] = []
    for ordinal, item_in in enumerate(payload.items):
        normalized = _normalize_path(item_in.relative_path)
        item = ImportItem(
            import_batch_id=batch.id,
            firm_id=firm_id,
            ordinal=ordinal,
            relative_path=item_in.relative_path,
            normalized_relative_path=normalized,
            filename=item_in.filename,
            expected_bytes=item_in.expected_bytes,
            mime_type=item_in.mime_type,
            conflict_override=item_in.conflict_override.value if item_in.conflict_override else None,
        )
        db.add(item)
        items.append(item)

    db.commit()
    db.refresh(batch)
    for item in items:
        db.refresh(item)

    return batch, items


def confirm_batch(
    *,
    db: Session,
    firm_id: UUID,
    batch_id: UUID,
    user: User,
) -> tuple[ImportBatch, list[ImportItem]]:
    """Transition a draft batch to confirmed status.

    Re-validates the trio check because permissions could have changed
    between draft creation and confirmation. Refuses if the batch is not
    in draft status or has zero items.
    """
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == batch_id,
        ImportBatch.firm_id == firm_id,
    ).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    assert_can_bulk_import(
        db=db,
        user=user,
        scope=batch.scope,
        engagement_id=batch.engagement_id,
        firm_id=firm_id,
    )

    if batch.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch is already in '{batch.status}' status and cannot be confirmed again",
        )

    if batch.total_files == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot confirm a batch with no items",
        )

    batch.status = "confirmed"
    batch.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)

    items = db.query(ImportItem).filter(
        ImportItem.import_batch_id == batch_id,
        ImportItem.firm_id == firm_id,
    ).order_by(ImportItem.ordinal).all()

    return batch, items


def get_batch(
    *,
    db: Session,
    firm_id: UUID,
    batch_id: UUID,
    user: User,
) -> tuple[ImportBatch, list[ImportItem]]:
    """Fetch a batch and its items, enforcing the same trio check as create/confirm.

    Read access uses the trio gate because batch contents (planned filenames and
    paths) are engagement-scoped data. A plain staff member without trio
    membership has no business seeing another team member's planned import.
    """
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == batch_id,
        ImportBatch.firm_id == firm_id,
    ).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")

    assert_can_bulk_import(
        db=db,
        user=user,
        scope=batch.scope,
        engagement_id=batch.engagement_id,
        firm_id=firm_id,
    )

    items = db.query(ImportItem).filter(
        ImportItem.import_batch_id == batch_id,
        ImportItem.firm_id == firm_id,
    ).order_by(ImportItem.ordinal).all()

    return batch, items


# ---------------------------------------------------------------------------
# Phase 3: staging upload URL issuance and upload-complete verification
# ---------------------------------------------------------------------------

# Error codes written to ImportItem.error_code on failure.
ERROR_FILE_TOO_LARGE = "FILE_TOO_LARGE"

MAX_DIRECT_UPLOAD_BYTES = 250 * 1024 * 1024  # 250 MB, matching document_service.py


def _get_batch_for_firm(
    db: Session,
    firm_id: UUID,
    batch_id: UUID,
) -> "ImportBatch":
    """Fetch a batch by id and firm_id only. No status validation here --
    status is checked only after the caller's auth check has run, so
    an unauthorized caller cannot learn batch state before being refused."""
    batch = db.query(ImportBatch).filter(
        ImportBatch.id == batch_id,
        ImportBatch.firm_id == firm_id,
    ).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")
    return batch


def issue_item_upload_url(
    *,
    db: Session,
    firm_id: UUID,
    batch_id: UUID,
    item_id: UUID,
    user: User,
) -> dict:
    """Issue a presigned PUT URL for one item's staging upload.

    Re-runs assert_can_bulk_import: trio eligibility must hold at every step,
    not just at batch creation or confirmation time.
    The item status remains planned after this call; it advances to uploaded
    only once the browser confirms via complete_item_upload.
    """
    from app.services import s3 as s3_service

    # 1. Existence check only -- no status validation yet.
    batch = _get_batch_for_firm(db, firm_id, batch_id)

    # 2. Auth check before revealing any batch state to the caller.
    assert_can_bulk_import(
        db=db,
        user=user,
        scope=batch.scope,
        engagement_id=batch.engagement_id,
        firm_id=firm_id,
    )

    # 3. Status and item validation -- only reached by authorized callers.
    if batch.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch must be in confirmed status for uploads; current status is '{batch.status}'",
        )

    item = db.query(ImportItem).filter(
        ImportItem.id == item_id,
        ImportItem.import_batch_id == batch_id,
        ImportItem.firm_id == firm_id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import item not found")

    if item.status != "planned":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Item is in '{item.status}' status; upload URL can only be issued for planned items",
        )

    staging_key = f"staging/{firm_id}/{batch_id}/{item_id}"
    content_type = item.mime_type or "application/octet-stream"
    upload_url = s3_service.generate_presigned_put_url(staging_key, content_type)

    item.staging_s3_key = staging_key
    db.commit()

    return {
        "item_id": item_id,
        "upload_url": upload_url,
        "staging_s3_key": staging_key,
        "expires_in_seconds": s3_service.PRESIGNED_URL_EXPIRY,
    }


def complete_item_upload(
    *,
    db: Session,
    firm_id: UUID,
    batch_id: UUID,
    item_id: UUID,
    user: User,
) -> "ImportItem":
    """Verify a staging upload and advance the item to uploaded status.

    Re-runs assert_can_bulk_import before touching anything, matching
    complete_upload's documented reasoning: permissions can change between
    URL issuance and this call.

    Size check rationale:
    - Hard limit: actual size > MAX_DIRECT_UPLOAD_BYTES -> delete, fail FILE_TOO_LARGE.
    - The browser's File.size is exact by definition (JS File API). If the actual
      S3 ContentLength differs from expected_bytes by more than 1024 bytes, that
      is noted in error_detail but does not block the upload -- minor platform
      differences exist, and the hard limit is the security-relevant gate.
    - attempt_count is incremented on every call regardless of outcome, since
      this represents a real attempt at completing the upload.
    """
    from botocore.exceptions import ClientError
    from app.services import s3 as s3_service
    from datetime import datetime, timezone

    # 1. Existence check only -- no status validation yet.
    batch = _get_batch_for_firm(db, firm_id, batch_id)

    # 2. Auth check before revealing any batch state to the caller.
    assert_can_bulk_import(
        db=db,
        user=user,
        scope=batch.scope,
        engagement_id=batch.engagement_id,
        firm_id=firm_id,
    )

    # 3. Status and item validation -- only reached by authorized callers.
    if batch.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch must be in confirmed status for uploads; current status is '{batch.status}'",
        )

    item = db.query(ImportItem).filter(
        ImportItem.id == item_id,
        ImportItem.import_batch_id == batch_id,
        ImportItem.firm_id == firm_id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import item not found")

    if item.status != "planned":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Item is in '{item.status}' status; upload-complete only applies to planned items",
        )

    if not item.staging_s3_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No staging upload URL was issued for this item; call upload-url first",
        )

    item.attempt_count = (item.attempt_count or 0) + 1

    # Verify the staging object exists and check its size.
    try:
        meta = s3_service.head_object(item.staging_s3_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staged upload not found -- the file was not uploaded to the provided URL",
            )
        db.commit()
        raise

    size_bytes = meta.get("ContentLength", 0)

    if size_bytes > MAX_DIRECT_UPLOAD_BYTES:
        s3_service.delete_object(item.staging_s3_key)
        item.status = "failed"
        item.error_code = ERROR_FILE_TOO_LARGE
        item.error_detail = (
            f"File size {size_bytes} bytes exceeds the {MAX_DIRECT_UPLOAD_BYTES // (1024 * 1024)} MB limit"
        )
        item.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=item.error_detail,
        )

    # Note any meaningful size discrepancy in error_detail for auditability,
    # but do not fail the upload -- the hard limit is the security gate.
    size_note = None
    if abs(size_bytes - item.expected_bytes) > 1024:
        size_note = (
            f"Actual size {size_bytes} bytes differs from expected {item.expected_bytes} bytes"
        )

    item.status = "uploaded"
    item.error_detail = size_note
    item.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Phase 4 read path: conflict preview
# ---------------------------------------------------------------------------

def preview_batch(
    *,
    db: Session,
    firm_id: UUID,
    batch_id: UUID,
    user: User,
) -> list[dict]:
    """Read-only conflict preview for a batch in draft or confirmed status.

    For each item, resolves the destination path (read-only folder lookup only)
    and checks whether a live document with the same filename already exists
    at that location. No folder is created, no S3 call is made, and no
    database row is written.
    """
    from app.services.import_finalization_service import (
        _resolve_destination_folder_readonly,
        _find_duplicate,
    )

    # 1. Existence check only -- no status validation yet.
    batch = _get_batch_for_firm(db, firm_id, batch_id)

    # 2. Auth check before revealing any batch state to the caller.
    assert_can_bulk_import(
        db=db,
        user=user,
        scope=batch.scope,
        engagement_id=batch.engagement_id,
        firm_id=firm_id,
    )

    # 3. Status validation -- only reached by authorized callers.
    if batch.status not in ("draft", "confirmed"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Preview is only available for batches in draft or confirmed status; current status is '{batch.status}'",
        )

    items = db.query(ImportItem).filter(
        ImportItem.import_batch_id == batch_id,
        ImportItem.firm_id == firm_id,
    ).order_by(ImportItem.ordinal).all()

    results = []
    for item in items:
        dest_folder_id, resolved = _resolve_destination_folder_readonly(
            db, batch, item.normalized_relative_path
        )
        has_conflict = False
        existing_document_id = None
        existing_document_filename = None

        if resolved:
            duplicate = _find_duplicate(db, batch, dest_folder_id, item.filename)
            if duplicate:
                has_conflict = True
                existing_document_id = duplicate.id
                existing_document_filename = duplicate.filename

        results.append({
            "item_id": item.id,
            "resolved": resolved,
            "has_conflict": has_conflict,
            "existing_document_id": existing_document_id,
            "existing_document_filename": existing_document_filename,
        })

    return results
