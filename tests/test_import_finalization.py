# tests/test_import_finalization.py
"""
Guard tests for import finalization Phase 4 (process_import_tick, recover_expired_leases).

The finalization functions are called directly as Python functions rather than
waiting for real scheduler timing, since the scheduler is not started in tests.

S3 calls are mocked via patch("app.services.s3.*") matching the pattern
already used in test_filesystem_phase4_task2.py.

Tests:
  (a) Fully uploaded single-item batch -> Document created, item completed, batch closed.
  (b) Idempotency: item with existing final_document_id is not duplicated.
      Watched red by temporarily removing the idempotency fence.
  (c) Lease recovery: expired processing item is reset then finalized.
      Watched red by temporarily disabling the reset.
  (d) Conflict policies: skip, replace (soft-delete), keep_both (suffix).
  (e) Depth enforcement: path exceeding MAX_FOLDER_DEPTH fails the item cleanly.
      Watched red by bypassing create_folder with a raw insert.
  (f) One item's failure does not prevent other items in the same tick from completing.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.document import Document
from app.models.import_batch import ImportBatch
from app.models.import_item import ImportItem
from app.models.user import User
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_owner():
    from app.models.firm import Firm
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Fin Test {uuid.uuid4()}", slug=f"ft-{uuid.uuid4().hex[:8]}")
        db.add(firm)
        db.flush()
        owner = User(
            firm_id=firm.id,
            email=f"owner-{uuid.uuid4().hex[:8]}@fin.test",
            hashed_password=get_password_hash("x"),
            full_name="Owner",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        return firm.id, owner.id
    finally:
        db.close()


def _make_client(firm_id):
    from app.models.client import Client
    db = TestingSessionLocal()
    try:
        c = Client(firm_id=firm_id, name=f"Client-{uuid.uuid4().hex[:6]}")
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def _make_engagement(firm_id, client_id):
    from app.models.engagement import Engagement
    db = TestingSessionLocal()
    try:
        e = Engagement(firm_id=firm_id, client_id=client_id, name=f"Eng-{uuid.uuid4().hex[:6]}")
        db.add(e)
        db.commit()
        return e.id
    finally:
        db.close()


def _make_batch(firm_id, client_id, engagement_id, owner_id, status="confirmed"):
    db = TestingSessionLocal()
    try:
        batch = ImportBatch(
            firm_id=firm_id,
            created_by_user_id=owner_id,
            scope="engagement",
            client_id=client_id,
            engagement_id=engagement_id,
            conflict_policy="skip",
            status=status,
            total_files=1,
            total_bytes=1024,
            confirmed_at=datetime.now(timezone.utc) if status == "confirmed" else None,
        )
        db.add(batch)
        db.commit()
        return batch.id
    finally:
        db.close()


def _make_item(firm_id, batch_id, relative_path="file.pdf", status="uploaded",
               staging_s3_key=None, final_document_id=None,
               lease_expires_at=None, claimed_by=None):
    db = TestingSessionLocal()
    try:
        item = ImportItem(
            import_batch_id=batch_id,
            firm_id=firm_id,
            ordinal=0,
            relative_path=relative_path,
            normalized_relative_path=relative_path,
            filename=relative_path.split("/")[-1],
            expected_bytes=1024,
            mime_type="application/pdf",
            status=status,
            staging_s3_key=staging_s3_key or f"staging/{firm_id}/{batch_id}/{uuid.uuid4()}",
            final_document_id=final_document_id,
            lease_expires_at=lease_expires_at,
            claimed_by=claimed_by,
        )
        db.add(item)
        db.commit()
        return item.id
    finally:
        db.close()


def _get_item(item_id):
    db = TestingSessionLocal()
    try:
        item = db.query(ImportItem).filter(ImportItem.id == item_id).first()
        return {
            "status": item.status,
            "final_document_id": item.final_document_id,
            "error_code": item.error_code,
            "claimed_by": item.claimed_by,
            "attempt_count": item.attempt_count,
        }
    finally:
        db.close()


def _get_batch(batch_id):
    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        return {"status": b.status, "completed_files": b.completed_files, "failed_files": b.failed_files}
    finally:
        db.close()


def _count_docs(firm_id, engagement_id):
    db = TestingSessionLocal()
    try:
        return db.query(Document).filter(
            Document.firm_id == firm_id,
            Document.engagement_id == engagement_id,
            Document.deleted_at.is_(None),
        ).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (a): fully uploaded batch produces a Document and closes the batch
# ---------------------------------------------------------------------------

def test_process_tick_finalizes_uploaded_item_and_closes_batch():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)
    item_id = _make_item(firm_id, batch_id, relative_path="report.pdf")

    with patch("app.services.s3.copy_object_within_bucket") as mock_copy, \
         patch("app.services.s3.delete_object") as mock_del:
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    item = _get_item(item_id)
    assert item["status"] == "completed", f"Expected completed, got {item['status']}"
    assert item["final_document_id"] is not None
    assert item["claimed_by"] is None

    assert _count_docs(firm_id, eng_id) == 1
    assert mock_copy.called
    assert mock_del.called

    batch = _get_batch(batch_id)
    assert batch["status"] == "completed"
    assert batch["completed_files"] == 1


# ---------------------------------------------------------------------------
# Test (b): idempotency -- item with final_document_id is not duplicated
# ---------------------------------------------------------------------------

def test_idempotency_existing_final_document_id_not_duplicated():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)

    # First run: finalize normally
    item_id = _make_item(firm_id, batch_id, relative_path="doc.pdf")
    with patch("app.services.s3.copy_object_within_bucket"), \
         patch("app.services.s3.delete_object"):
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    assert _count_docs(firm_id, eng_id) == 1
    first_doc_id = _get_item(item_id)["final_document_id"]

    # Reset item status to uploaded to simulate a re-run
    db = TestingSessionLocal()
    try:
        item = db.query(ImportItem).filter(ImportItem.id == item_id).first()
        item.status = "uploaded"
        item.staging_s3_key = f"staging/{firm_id}/{batch_id}/{uuid.uuid4()}"
        db.commit()
    finally:
        db.close()

    # Use keep_both policy so that WITHOUT the fence a second Document would be created.
    # WITH the fence, the item short-circuits and nothing is created.
    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        b.conflict_policy = "keep_both"
        db.commit()
    finally:
        db.close()

    # Second run: should detect final_document_id and not create a second Document
    with patch("app.services.s3.copy_object_within_bucket") as mock_copy2, \
         patch("app.services.s3.delete_object"):
        process_import_tick(batch_size=10)

    assert _count_docs(firm_id, eng_id) == 1, "Idempotency failed: second Document was created"
    assert not mock_copy2.called, "copy_object_within_bucket should not have been called on re-run"


# ---------------------------------------------------------------------------
# Test (c): lease recovery resets stuck items and allows re-finalization
# ---------------------------------------------------------------------------

def test_recover_expired_leases_resets_then_finalizes():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)

    expired = datetime.now(timezone.utc) - timedelta(minutes=10)
    item_id = _make_item(
        firm_id, batch_id,
        status="processing",
        lease_expires_at=expired,
        claimed_by="dead-worker",
    )

    from app.services.import_finalization_service import recover_expired_leases, process_import_tick

    # --- RED phase ---
    # Call a version of recover_expired_leases that finds the stale item but rolls back
    # instead of committing — simulating a missing db.commit() call (the bug we guard against).
    def _broken_recover():
        from app.db.session import SessionLocal
        from app.models.import_item import ImportItem
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            stale = db.query(ImportItem).filter(
                ImportItem.status == "processing",
                ImportItem.lease_expires_at < now,
            ).all()
            for s in stale:
                s.status = "uploaded"
                s.claimed_by = None
                s.lease_expires_at = None
            db.rollback()  # BUG: missing commit — change never persists
        finally:
            db.close()

    _broken_recover()

    # process_import_tick only queries status='uploaded'; the stuck item is invisible to it.
    with patch("app.services.s3.copy_object_within_bucket"), \
         patch("app.services.s3.delete_object"):
        process_import_tick(batch_size=10)

    stuck = _get_item(item_id)
    assert stuck["status"] == "processing", (
        f"RED: item should remain 'processing' when reset does not commit; "
        f"got '{stuck['status']}'"
    )
    # Watched-fail: replacing _broken_recover() with the real recover_expired_leases() above
    # and asserting 'processing' here fails with:
    #   AssertionError: RED: item should remain 'processing' when reset does not commit;
    #   got 'uploaded'

    # --- GREEN phase: real recover_expired_leases resets the item ---
    recover_expired_leases()

    item = _get_item(item_id)
    assert item["status"] == "uploaded", (
        f"Expected 'uploaded' after real recovery, got '{item['status']}'"
    )
    assert item["claimed_by"] is None

    with patch("app.services.s3.copy_object_within_bucket"), \
         patch("app.services.s3.delete_object"):
        process_import_tick(batch_size=10)

    assert _get_item(item_id)["status"] == "completed", (
        f"Expected 'completed' after tick, got '{_get_item(item_id)['status']}'"
    )


# ---------------------------------------------------------------------------
# Test (d): conflict policies skip, replace (soft-delete), keep_both (suffix)
# ---------------------------------------------------------------------------

def test_conflict_skip_leaves_existing_document_and_marks_skipped():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)

    # Pre-existing document with same name at root
    db = TestingSessionLocal()
    try:
        existing = Document(
            firm_id=firm_id, client_id=client_id, engagement_id=eng_id,
            scope="engagement", filename="report.pdf",
            s3_key=f"{firm_id}/{client_id}/{eng_id}/{uuid.uuid4()}/report.pdf",
            content_type="application/pdf", size_bytes=512,
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id
    finally:
        db.close()

    # Override batch conflict_policy to skip
    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        b.conflict_policy = "skip"
        db.commit()
    finally:
        db.close()

    item_id = _make_item(firm_id, batch_id, relative_path="report.pdf")

    with patch("app.services.s3.copy_object_within_bucket") as mock_copy, \
         patch("app.services.s3.delete_object"):
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    assert _get_item(item_id)["status"] == "skipped"
    assert _count_docs(firm_id, eng_id) == 1  # original still live, no new one
    assert not mock_copy.called


def test_conflict_replace_soft_deletes_existing_and_creates_new():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)

    db = TestingSessionLocal()
    try:
        existing = Document(
            firm_id=firm_id, client_id=client_id, engagement_id=eng_id,
            scope="engagement", filename="report.pdf",
            s3_key=f"{firm_id}/{client_id}/{eng_id}/{uuid.uuid4()}/report.pdf",
            content_type="application/pdf", size_bytes=512,
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        b.conflict_policy = "replace"
        db.commit()
    finally:
        db.close()

    item_id = _make_item(firm_id, batch_id, relative_path="report.pdf")

    with patch("app.services.s3.copy_object_within_bucket"), \
         patch("app.services.s3.delete_object"):
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    assert _get_item(item_id)["status"] == "completed"
    # Exactly one live document (new one); original is soft-deleted
    assert _count_docs(firm_id, eng_id) == 1
    db = TestingSessionLocal()
    try:
        old_doc = db.query(Document).filter(Document.id == existing_id).first()
        assert old_doc.deleted_at is not None, "Old document must be soft-deleted, not hard-deleted"
    finally:
        db.close()


def test_conflict_keep_both_creates_suffixed_document():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)

    db = TestingSessionLocal()
    try:
        existing = Document(
            firm_id=firm_id, client_id=client_id, engagement_id=eng_id,
            scope="engagement", filename="report.pdf",
            s3_key=f"{firm_id}/{client_id}/{eng_id}/{uuid.uuid4()}/report.pdf",
            content_type="application/pdf", size_bytes=512,
        )
        db.add(existing)
        db.commit()
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        b.conflict_policy = "keep_both"
        db.commit()
    finally:
        db.close()

    item_id = _make_item(firm_id, batch_id, relative_path="report.pdf")

    with patch("app.services.s3.copy_object_within_bucket"), \
         patch("app.services.s3.delete_object"):
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    assert _get_item(item_id)["status"] == "completed"
    # Both original and suffixed version are live
    assert _count_docs(firm_id, eng_id) == 2
    db = TestingSessionLocal()
    try:
        docs = db.query(Document).filter(
            Document.firm_id == firm_id,
            Document.engagement_id == eng_id,
            Document.deleted_at.is_(None),
        ).all()
        names = sorted(d.filename for d in docs)
        assert "report (2).pdf" in names, f"Expected suffixed filename, got: {names}"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test (e): path exceeding MAX_FOLDER_DEPTH fails the item cleanly
# ---------------------------------------------------------------------------

def test_depth_exceeded_fails_item_cleanly():
    from app.services.document_folder_service import MAX_FOLDER_DEPTH

    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id)

    # Build a path deeper than MAX_FOLDER_DEPTH
    deep_path = "/".join([f"Folder{i}" for i in range(MAX_FOLDER_DEPTH + 2)] + ["file.pdf"])
    item_id = _make_item(firm_id, batch_id, relative_path=deep_path)

    with patch("app.services.s3.copy_object_within_bucket"), \
         patch("app.services.s3.delete_object"):
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    item = _get_item(item_id)
    assert item["status"] == "failed", f"Expected failed, got {item['status']}"
    assert item["error_code"] is not None
    assert _count_docs(firm_id, eng_id) == 0


# ---------------------------------------------------------------------------
# Test (f): one item's failure does not block other items in the same tick
# ---------------------------------------------------------------------------

def test_one_item_failure_does_not_block_others():
    firm_id, owner_id = _make_firm_and_owner()
    client_id = _make_client(firm_id)
    eng_id = _make_engagement(firm_id, client_id)
    batch_id = _make_batch(firm_id, client_id, eng_id, owner_id, status="confirmed")

    db = TestingSessionLocal()
    try:
        b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        b.total_files = 2
        db.commit()
    finally:
        db.close()

    # Explicit, known staging keys so the mock can key deterministically off the source
    # argument (item.staging_s3_key) rather than a fragile substring match on the dest key.
    good_staging_key = f"staging/{firm_id}/{batch_id}/good-{uuid.uuid4()}"
    bad_staging_key = f"staging/{firm_id}/{batch_id}/bad-{uuid.uuid4()}"

    good_item_id = _make_item(firm_id, batch_id, relative_path="good.pdf",
                              staging_s3_key=good_staging_key)
    bad_item_id = _make_item(firm_id, batch_id, relative_path="bad.pdf",
                             staging_s3_key=bad_staging_key)

    def selective_copy(source, dest):
        """Fail on the bad item's known staging key; succeed silently on the good one."""
        if source == bad_staging_key:
            raise RuntimeError("simulated S3 failure on bad item")

    with patch("app.services.s3.copy_object_within_bucket", side_effect=selective_copy), \
         patch("app.services.s3.delete_object"):
        from app.services.import_finalization_service import process_import_tick
        process_import_tick(batch_size=10)

    good = _get_item(good_item_id)
    bad = _get_item(bad_item_id)

    assert good["status"] == "completed", (
        f"Expected good item 'completed', got '{good['status']}' -- "
        f"bad item failure may have leaked into good item's session"
    )
    assert good["final_document_id"] is not None, (
        "Good item must have a final_document_id"
    )

    assert bad["status"] == "failed", (
        f"Expected bad item 'failed', got '{bad['status']}'"
    )
    assert bad["error_code"] is not None, (
        f"Bad item must have an error_code; got None"
    )
