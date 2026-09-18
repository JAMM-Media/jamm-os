# app/api/import_batches.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.import_batch import ImportBatchCreate, ImportBatchOut, ImportItemOut, ItemUploadUrlOut
import app.services.import_batch_service as import_batch_service

router = APIRouter(prefix="/import-batches", tags=["Import Batches"])


def _build_out(batch, items) -> ImportBatchOut:
    """Assemble the response model from the batch ORM object and its items list."""
    return ImportBatchOut.model_validate(batch).model_copy(
        update={"items": [ImportItemOut.model_validate(i) for i in items]}
    )


@router.post("/", response_model=ImportBatchOut, status_code=201)
def create_draft(
    payload: ImportBatchCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Create an import batch in draft status.

    The trio check (engagement administrator, manager, or firm owner) is
    enforced inside the service, following the two-layer pattern used by
    approve, reassign, and delete endpoints.
    """
    batch, items = import_batch_service.create_draft(
        db=db,
        firm_id=current_firm.id,
        user=current_user,
        payload=payload,
    )
    return _build_out(batch, items)


@router.post("/{batch_id}/confirm", response_model=ImportBatchOut)
def confirm_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Confirm a draft batch, transitioning it to confirmed status.

    This is the point of no return before Phase 3 upload begins. The batch's
    items, destination, and conflict policy become immutable once confirmed.
    """
    batch, items = import_batch_service.confirm_batch(
        db=db,
        firm_id=current_firm.id,
        batch_id=batch_id,
        user=current_user,
    )
    return _build_out(batch, items)


@router.get("/{batch_id}", response_model=ImportBatchOut)
def get_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Fetch a batch and its items."""
    batch, items = import_batch_service.get_batch(
        db=db,
        firm_id=current_firm.id,
        batch_id=batch_id,
        user=current_user,
    )
    return _build_out(batch, items)


@router.post("/{batch_id}/items/{item_id}/upload-url", response_model=ItemUploadUrlOut)
def issue_item_upload_url(
    batch_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Issue a presigned PUT URL for staging one item's file upload to S3.

    The trio check is re-run here -- eligibility must hold at URL issuance time,
    not just at batch confirmation. Item status stays planned until upload-complete.
    """
    return import_batch_service.issue_item_upload_url(
        db=db,
        firm_id=current_firm.id,
        batch_id=batch_id,
        item_id=item_id,
        user=current_user,
    )


@router.post("/{batch_id}/items/{item_id}/upload-complete", response_model=ImportItemOut)
def complete_item_upload(
    batch_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    """Verify and record a completed staging upload, advancing the item to uploaded status.

    Re-runs the trio check before touching anything. Performs a HEAD request to
    confirm the object exists and check its size against MAX_DIRECT_UPLOAD_BYTES.
    """
    item = import_batch_service.complete_item_upload(
        db=db,
        firm_id=current_firm.id,
        batch_id=batch_id,
        item_id=item_id,
        user=current_user,
    )
    return ImportItemOut.model_validate(item)
