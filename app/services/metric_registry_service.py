# app/services/metric_registry_service.py

"""Validation and write door for the metric registry curation tables.

No router. The registry is authored content, never user-edited; the
authoring seed calls replace_axes and replace_relations so there is exactly
one door onto these tables.

NO BEHAVIORAL EVENT LOGGING. The registry and its child tables are
platform-global with no firm_id and are never edited by a firm, so there is
no firm to attribute an event to. This module does not call log_event and
must not start.

Axis key resolution (Sep 10, 2026 ruling R3). A database foreign key is
impossible across four sources, two of which are code constants, so the
rule lives here and is pinned by tests (ruling R7):

  engagement_category  -> ServiceCategory (code constant)
  complexity_flag      -> complexity_flags.key
  complexity_dimension -> the PAIR (complexity_flags.key,
                          complexity_dimensions.key), written
                          "flag_key.dimension_key", split on the first dot
  referral_source      -> ReferralSource (code constant)

Resolution is by key existence only; an inactive catalog flag still
resolves, because the registry is describing what a metric CAN be sliced
on, not what a firm currently offers.

Refusal convention: 422 means understood but not allowed (a key that does
not resolve, a duplicate, a self-relation); 404 means the metric is absent.
Refusal strings are surfaced verbatim by the frontend, so they name things
by label where a label exists and never by UUID.

Order of operations is the point of every write here: resolve, then check
duplicates, then insert. A refused write leaves nothing behind.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import MetricAxisKind, ReferralSource, ServiceCategory
from app.crud import metric_registry as crud
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_flag import ComplexityFlag
from app.models.metric_registry import MetricRegistry
from app.models.metric_registry_axis import MetricRegistryAxis
from app.models.metric_registry_relation import MetricRegistryRelation
from app.schemas.metric_registry_axis import (
    DIMENSION_KEY_SHAPE_MESSAGE,
    MetricRegistryAxisCreate,
    split_dimension_key,
)
from app.schemas.metric_registry_relation import (
    SELF_RELATION_MESSAGE,
    MetricRegistryRelationCreate,
)

NO_METRIC_MESSAGE = "No metric with that id."
DUPLICATE_AXIS_MESSAGE = "This metric already lists that axis."
DUPLICATE_RELATION_MESSAGE = "This metric already lists that related metric."


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _get_flag_by_key(db: Session, key: str) -> ComplexityFlag | None:
    return db.execute(
        select(ComplexityFlag).where(ComplexityFlag.key == key)
    ).scalar_one_or_none()


def _refuse(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def resolve_axis_key(db: Session, axis_kind: MetricAxisKind, axis_key: str) -> None:
    """Return None when axis_key resolves for axis_kind; raise 422 otherwise.

    Implements ruling R3 exactly. See the module docstring for the table.
    """
    if axis_kind == MetricAxisKind.engagement_category:
        if axis_key not in {category.value for category in ServiceCategory}:
            valid = ", ".join(category.value for category in ServiceCategory)
            raise _refuse(
                f"Unknown engagement category '{axis_key}'. "
                f"Valid categories are: {valid}."
            )
        return

    if axis_kind == MetricAxisKind.complexity_flag:
        if _get_flag_by_key(db, axis_key) is None:
            raise _refuse(
                f"No complexity flag with key '{axis_key}' exists in the catalog."
            )
        return

    if axis_kind == MetricAxisKind.complexity_dimension:
        try:
            flag_key, dimension_key = split_dimension_key(axis_key)
        except ValueError:
            raise _refuse(DIMENSION_KEY_SHAPE_MESSAGE)
        flag = _get_flag_by_key(db, flag_key)
        if flag is None:
            raise _refuse(
                f"No complexity flag with key '{flag_key}' exists in the catalog."
            )
        dimension = db.execute(
            select(ComplexityDimension).where(
                ComplexityDimension.flag_id == flag.id,
                ComplexityDimension.key == dimension_key,
            )
        ).scalar_one_or_none()
        if dimension is None:
            # The flag's name is its display label, so the message uses it.
            raise _refuse(
                f"Complexity flag '{flag.name}' has no dimension with key "
                f"'{dimension_key}'."
            )
        return

    if axis_kind == MetricAxisKind.referral_source:
        if axis_key not in {source.value for source in ReferralSource}:
            raise _refuse(f"Unknown referral source '{axis_key}'.")
        return

    # Unreachable while MetricAxisKind has exactly four values; kept so a
    # fifth value added without a resolution rule refuses instead of passing.
    raise _refuse(f"No resolution rule exists for axis kind '{axis_kind}'.")


# ---------------------------------------------------------------------------
# Shared checks
# ---------------------------------------------------------------------------

def _require_metric(db: Session, metric_id: UUID) -> MetricRegistry:
    metric = crud.get_metric(db, metric_id)
    if metric is None:
        raise HTTPException(status_code=404, detail=NO_METRIC_MESSAGE)
    return metric


def _require_payload_targets_metric(payload_metric_id: UUID, metric_id: UUID) -> None:
    if payload_metric_id != metric_id:
        raise _refuse(
            "The payload names a different metric than the one being edited."
        )


def _validate_relation(
    db: Session, metric: MetricRegistry, payload: MetricRegistryRelationCreate
) -> None:
    """Every refusal a relation can earn, in order, writing nothing."""
    _require_payload_targets_metric(payload.metric_id, metric.id)
    if payload.related_metric_id == metric.id:
        # Belt to the schema's braces; a payload built with model_construct
        # skips the schema validator.
        raise _refuse(SELF_RELATION_MESSAGE)
    if crud.get_metric(db, payload.related_metric_id) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Metric '{metric.key}' names a related metric that does not exist."
            ),
        )


def _validate_axis(
    db: Session, metric: MetricRegistry, payload: MetricRegistryAxisCreate
) -> None:
    _require_payload_targets_metric(payload.metric_id, metric.id)
    resolve_axis_key(db, payload.axis_kind, payload.axis_key)


# ---------------------------------------------------------------------------
# Single writes
# ---------------------------------------------------------------------------

def add_axis(
    db: Session, metric_id: UUID, payload: MetricRegistryAxisCreate
) -> MetricRegistryAxis:
    """Resolve first, then check for a duplicate, then insert.

    A refused axis writes nothing. The duplicate is found by a read before
    the insert, not by catching IntegrityError, so the session is never left
    in a failed state and the message is ours.
    """
    metric = _require_metric(db, metric_id)
    _validate_axis(db, metric, payload)
    if crud.get_axis(db, metric.id, payload.axis_kind, payload.axis_key) is not None:
        raise _refuse(DUPLICATE_AXIS_MESSAGE)

    row = MetricRegistryAxis(
        metric_id=metric.id,
        axis_kind=payload.axis_kind,
        axis_key=payload.axis_key,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_relation(
    db: Session, metric_id: UUID, payload: MetricRegistryRelationCreate
) -> MetricRegistryRelation:
    """Both metrics must exist, no self-relation, no duplicate pair, then insert.

    404 names which side is missing: the source side can only say "No metric
    with that id." because there is no row to read a key from; the related
    side names the source metric by key.
    """
    metric = _require_metric(db, metric_id)
    _validate_relation(db, metric, payload)
    if crud.get_relation(db, metric.id, payload.related_metric_id) is not None:
        raise _refuse(DUPLICATE_RELATION_MESSAGE)

    row = MetricRegistryRelation(
        metric_id=metric.id,
        related_metric_id=payload.related_metric_id,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Whole-list replacement: the door the authoring seed uses
# ---------------------------------------------------------------------------

def _refuse_duplicates_within(items: list[tuple], what: str) -> None:
    seen: set[tuple] = set()
    for item in items:
        if item in seen:
            raise _refuse(
                f"The replacement lists the same {what} more than once."
            )
        seen.add(item)


def replace_axes(
    db: Session, metric_id: UUID, payloads: list[MetricRegistryAxisCreate]
) -> list[MetricRegistryAxis]:
    """Validate EVERY item, then delete-and-insert in one transaction.

    A single bad item refuses the whole replacement and writes nothing:
    nothing is deleted until every item has resolved.
    """
    metric = _require_metric(db, metric_id)
    for payload in payloads:
        _validate_axis(db, metric, payload)
    _refuse_duplicates_within(
        [(p.axis_kind, p.axis_key) for p in payloads], "axis"
    )

    try:
        for existing in crud.list_axes_for_metric(db, metric.id):
            db.delete(existing)
        db.flush()
        rows = [
            MetricRegistryAxis(
                metric_id=metric.id,
                axis_kind=p.axis_kind,
                axis_key=p.axis_key,
                sort_order=p.sort_order,
            )
            for p in payloads
        ]
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return crud.list_axes_for_metric(db, metric.id)


def replace_relations(
    db: Session, metric_id: UUID, payloads: list[MetricRegistryRelationCreate]
) -> list[MetricRegistryRelation]:
    """Validate EVERY item, then delete-and-insert in one transaction.

    Same contract as replace_axes: one bad item, nothing written.
    """
    metric = _require_metric(db, metric_id)
    for payload in payloads:
        _validate_relation(db, metric, payload)
    _refuse_duplicates_within(
        [(p.related_metric_id,) for p in payloads], "related metric"
    )

    try:
        for existing in crud.list_relations_for_metric(db, metric.id):
            db.delete(existing)
        db.flush()
        rows = [
            MetricRegistryRelation(
                metric_id=metric.id,
                related_metric_id=p.related_metric_id,
                sort_order=p.sort_order,
            )
            for p in payloads
        ]
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return crud.list_relations_for_metric(db, metric.id)
