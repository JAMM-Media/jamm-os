# app/services/import_finalization_service.py

"""
Import finalization service -- Phase 4: APScheduler-driven item finalization.

This is the only phase that creates real Document rows. It runs as an interval
job on the scheduler, not in response to an HTTP request.

Architecture (per the Phase 1 design):
  - Claim: short transaction, FOR UPDATE SKIP LOCKED, commit before any S3 work.
  - Finalize each item outside any held lock (one DB session per item).
  - Idempotency fence: final_document_id on the item row is set atomically with
    the Document creation; a re-run after a crash never creates a second Document.
  - recover_expired_leases: a separate, less-frequent sweep that releases any
    item stuck in 'processing' with an expired lease, so crashed ticks are
    recoverable.

New patterns introduced here (neither existed in this codebase before Phase 4):
  - trigger="interval" scheduler jobs.
  - SELECT FOR UPDATE SKIP LOCKED (booking_service uses FOR UPDATE without skip_locked).
  - get_document_folder_by_name (no prior folder-by-name lookup existed).
"""

import logging
import os
import uuid as _uuid_module
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

log = logging.getLogger(__name__)

_LEASE_MINUTES = 5
_ERROR_DEPTH_EXCEEDED = "FOLDER_DEPTH_EXCEEDED"
_ERROR_FINALIZATION = "FINALIZATION_ERROR"


def _resolve_destination_folder(
    db,
    batch,
    normalized_relative_path: str,
) -> Optional[UUID]:
    """Walk the directory components of normalized_relative_path, creating any
    missing folders via create_folder (which enforces the depth-20 tripwire).

    Returns the UUID of the immediate parent folder for the file, or None if the
    file should sit at the batch's destination root (no subdirectory components).
    Raises HTTPException if create_folder refuses a depth violation.
    """
    from app.crud.document_folder import get_document_folder_by_name
    from app.services.document_folder_service import create_folder

    parts = normalized_relative_path.split("/")
    dir_parts = parts[:-1]   # everything before the filename

    parent_folder_id = batch.destination_folder_id

    for folder_name in dir_parts:
        if not folder_name:
            continue
        existing = get_document_folder_by_name(
            db,
            firm_id=batch.firm_id,
            scope=batch.scope,
            parent_folder_id=parent_folder_id,
            name=folder_name,
        )
        if existing:
            parent_folder_id = existing.id
        else:
            new_folder = create_folder(
                db=db,
                firm_id=batch.firm_id,
                scope=batch.scope,
                name=folder_name,
                client_id=batch.client_id,
                engagement_id=batch.engagement_id,
                parent_folder_id=parent_folder_id,
            )
            parent_folder_id = new_folder.id

    return parent_folder_id


def _build_final_s3_key(batch, doc_id: UUID, filename: str) -> str:
    """Build the permanent S3 key for a finalized document.

    Matches _build_s3_key's exact convention from document_service.py:
      engagement scope:   {firm_id}/{client_id}/{engagement_id}/{doc_id}/{filename}
      client scope:       {firm_id}/{client_id}/permanent/{doc_id}/{filename}
      firm_library scope: {firm_id}/firm_library/{doc_id}/{filename}
    """
    if batch.engagement_id is not None:
        return f"{batch.firm_id}/{batch.client_id}/{batch.engagement_id}/{doc_id}/{filename}"
    elif batch.client_id is not None:
        return f"{batch.firm_id}/{batch.client_id}/permanent/{doc_id}/{filename}"
    else:
        return f"{batch.firm_id}/firm_library/{doc_id}/{filename}"


def _find_duplicate(db, batch, folder_id: Optional[UUID], filename: str):
    """Return a live document in the target folder with the same filename, or None."""
    from app.models.document import Document
    query = db.query(Document).filter(
        Document.firm_id == batch.firm_id,
        Document.engagement_id == batch.engagement_id,
        Document.filename == filename,
        Document.deleted_at.is_(None),
    )
    if folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)
    else:
        query = query.filter(Document.folder_id.is_(None))
    return query.first()


def _finalize_one_item(db, item_id: UUID) -> None:
    """Finalize a single import item outside any held lock. Each item gets its
    own fresh DB state so a crash in one item never corrupts another."""
    from app.models.import_item import ImportItem
    from app.models.import_batch import ImportBatch
    from app.models.document import Document
    from app.crud.document import create_document, next_available_filename
    from app.services.s3 import copy_object_within_bucket, delete_object

    now = datetime.now(timezone.utc)

    item = db.query(ImportItem).filter(ImportItem.id == item_id).first()
    if item is None:
        log.warning("import_finalization: item %s not found, skipping", item_id)
        return

    batch = db.query(ImportBatch).filter(ImportBatch.id == item.import_batch_id).first()
    if batch is None:
        log.error("import_finalization: batch for item %s not found", item_id)
        item.status = "failed"
        item.error_code = _ERROR_FINALIZATION
        item.error_detail = "Parent batch not found"
        item.claimed_by = None
        item.lease_expires_at = None
        item.completed_at = now
        db.commit()
        return

    # Idempotency fence: if final_document_id is already set, a prior attempt
    # succeeded up through Document creation. Skip straight to completed.
    if item.final_document_id is not None:
        item.status = "completed"
        item.claimed_by = None
        item.lease_expires_at = None
        if item.completed_at is None:
            item.completed_at = now
        db.commit()
        log.info("import_finalization: item %s already has final_document_id, marking completed", item_id)
        return

    # Effective conflict policy: per-item override or batch default.
    conflict_policy = item.conflict_override or batch.conflict_policy

    try:
        # Resolve or create the destination folder tree.
        dest_folder_id = _resolve_destination_folder(db, batch, item.normalized_relative_path)

        actual_filename = item.filename

        # Check for an existing live document at the same location.
        duplicate = _find_duplicate(db, batch, dest_folder_id, actual_filename)

        if duplicate and conflict_policy == "skip":
            item.status = "skipped"
            item.claimed_by = None
            item.lease_expires_at = None
            item.completed_at = now
            db.commit()
            log.info(
                "import_finalization: item %s skipped -- duplicate '%s' exists",
                item_id, actual_filename,
            )
            return

        if duplicate and conflict_policy == "replace":
            # Soft-delete the existing document, matching this codebase's
            # standing rule: never hard-delete, always soft-delete.
            duplicate.deleted_at = now
            db.flush()

        if duplicate and conflict_policy == "keep_both":
            # Suffix the filename using the existing convention: "stem (N).ext"
            actual_filename = next_available_filename(
                db,
                firm_id=batch.firm_id,
                engagement_id=batch.engagement_id,
                folder_id=dest_folder_id,
                filename=actual_filename,
            )

        # Build the permanent S3 key and promote the staged object.
        final_doc_id = _uuid_module.uuid4()
        final_s3_key = _build_final_s3_key(batch, final_doc_id, actual_filename)

        copy_object_within_bucket(item.staging_s3_key, final_s3_key)
        # Only delete the staging object after the copy succeeds.
        delete_object(item.staging_s3_key)

        # Create the real Document row.
        doc = create_document(
            db=db,
            firm_id=batch.firm_id,
            client_id=batch.client_id,
            engagement_id=batch.engagement_id,
            uploaded_by=batch.created_by_user_id,
            filename=actual_filename,
            s3_key=final_s3_key,
            content_type=item.mime_type or "application/octet-stream",
            size_bytes=item.expected_bytes,
            doc_id=final_doc_id,
            source="staff",
        )
        if dest_folder_id is not None:
            doc.folder_id = dest_folder_id
            db.flush()

        # Stamp the idempotency fence and mark completed.
        item.final_document_id = doc.id
        item.final_folder_id = dest_folder_id
        item.status = "completed"
        item.claimed_by = None
        item.lease_expires_at = None
        item.completed_at = now
        db.commit()

        log.info(
            "import_finalization: item %s completed -> document %s at key %s",
            item_id, doc.id, final_s3_key,
        )

    except Exception as exc:
        log.error(
            "import_finalization: item %s failed: %s: %s",
            item_id, type(exc).__name__, exc,
        )
        db.rollback()
        # Re-fetch item after rollback to update its state.
        item = db.query(ImportItem).filter(ImportItem.id == item_id).first()
        if item is not None:
            item.status = "failed"
            item.error_code = _ERROR_FINALIZATION
            item.error_detail = f"{type(exc).__name__}: {exc}"[:512]
            item.claimed_by = None
            item.lease_expires_at = None
            item.completed_at = now
            db.commit()


def _maybe_close_batch(db, batch_id: UUID) -> None:
    """Transition a batch to a terminal status if all its items are terminal."""
    from app.models.import_batch import ImportBatch
    from app.models.import_item import ImportItem

    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if batch is None:
        return
    if batch.status in ("completed", "completed_with_errors", "canceled"):
        return

    # Count items by terminal status from real DB state, never from counters.
    from sqlalchemy import func
    status_counts = (
        db.query(ImportItem.status, func.count(ImportItem.id))
        .filter(ImportItem.import_batch_id == batch_id)
        .group_by(ImportItem.status)
        .all()
    )
    counts = {s: n for s, n in status_counts}
    total = sum(counts.values())
    terminal_count = sum(
        counts.get(s, 0) for s in ("completed", "skipped", "failed")
    )

    if terminal_count < total:
        return   # Some items are still in-flight.

    completed = counts.get("completed", 0)
    failed = counts.get("failed", 0)
    skipped = counts.get("skipped", 0)

    batch.completed_files = completed
    batch.failed_files = failed
    batch.skipped_files = skipped
    batch.status = "completed" if failed == 0 else "completed_with_errors"
    batch.finished_at = datetime.now(timezone.utc)
    db.commit()
    log.info(
        "import_finalization: batch %s closed as %s (completed=%d, failed=%d, skipped=%d)",
        batch_id, batch.status, completed, failed, skipped,
    )


def process_import_tick(batch_size: int = 5) -> None:
    """Claim a bounded slice of uploaded items and finalize each one.

    Interval-scheduled; the first interval job in this codebase. Called by
    APScheduler with max_instances=1 to prevent concurrent ticks overlapping.

    Session management: claim step uses a short transaction that commits before
    any S3 or folder work begins. Each item is then processed in its own fresh
    session so a crash in one item cannot corrupt another's state.
    """
    try:
        from app.db.session import SessionLocal
        from app.models.import_item import ImportItem
        from sqlalchemy import or_

        now = datetime.now(timezone.utc)
        worker_id = str(_uuid_module.uuid4())
        lease_deadline = now + timedelta(minutes=_LEASE_MINUTES)

        # --- Claim step: short transaction, commit before any S3 work ---
        claim_db = SessionLocal()
        item_ids: list[UUID] = []
        try:
            candidates = (
                claim_db.query(ImportItem)
                .filter(
                    ImportItem.status == "uploaded",
                    or_(
                        ImportItem.lease_expires_at.is_(None),
                        ImportItem.lease_expires_at < now,
                    ),
                )
                .with_for_update(skip_locked=True)
                .limit(batch_size)
                .all()
            )
            if not candidates:
                return

            for item in candidates:
                item.status = "processing"
                item.claimed_by = worker_id
                item.lease_expires_at = lease_deadline

            item_ids = [item.id for item in candidates]
            claim_db.commit()
        finally:
            claim_db.close()

        # --- Finalize each claimed item with its own fresh session ---
        batch_ids: set[UUID] = set()
        for item_id in item_ids:
            work_db = SessionLocal()
            try:
                from app.models.import_item import ImportItem as _II
                item_for_batch = work_db.query(_II).filter(_II.id == item_id).first()
                if item_for_batch:
                    batch_ids.add(item_for_batch.import_batch_id)
                _finalize_one_item(work_db, item_id)
            except Exception as exc:
                log.error(
                    "import_finalization: unexpected error finalizing item %s: %s",
                    item_id, exc, exc_info=True,
                )
            finally:
                work_db.close()

        # --- Check whether any batch is now fully terminal ---
        for batch_id in batch_ids:
            batch_db = SessionLocal()
            try:
                _maybe_close_batch(batch_db, batch_id)
            except Exception as exc:
                log.error(
                    "import_finalization: error closing batch %s: %s", batch_id, exc
                )
            finally:
                batch_db.close()

    except Exception as exc:
        log.error(
            "import_finalization: unhandled error in process_import_tick: %s",
            exc, exc_info=True,
        )


def recover_expired_leases() -> None:
    """Reset any item stuck in 'processing' with an expired lease back to 'uploaded'.

    Interval-scheduled at a longer cadence than process_import_tick so a
    crashed worker's items are eventually reclaimed and re-queued.
    """
    try:
        from app.db.session import SessionLocal
        from app.models.import_item import ImportItem

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            stale = db.query(ImportItem).filter(
                ImportItem.status == "processing",
                ImportItem.lease_expires_at < now,
            ).all()

            if not stale:
                return

            for item in stale:
                log.warning(
                    "import_finalization: reclaiming expired lease on item %s (was claimed by %s)",
                    item.id, item.claimed_by,
                )
                item.status = "uploaded"
                item.claimed_by = None
                item.lease_expires_at = None

            db.commit()
            log.info("import_finalization: recovered %d expired leases", len(stale))
        finally:
            db.close()

    except Exception as exc:
        log.error(
            "import_finalization: unhandled error in recover_expired_leases: %s",
            exc, exc_info=True,
        )
