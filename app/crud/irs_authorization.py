# app/crud/irs_authorization.py

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.irs_authorization import IrsAuthorization
from app.schemas.irs_authorization import IrsAuthorizationCreate, IrsAuthorizationUpdate


def create_irs_authorization(
    db: Session,
    auth_in: IrsAuthorizationCreate,
    firm_id: UUID,
) -> IrsAuthorization:
    auth = IrsAuthorization(**auth_in.model_dump(), firm_id=firm_id)
    db.add(auth)
    db.commit()
    db.refresh(auth)
    return auth


def get_irs_authorization(
    db: Session,
    auth_id: UUID,
    firm_id: UUID,
) -> IrsAuthorization | None:
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.id == auth_id,
            IrsAuthorization.firm_id == firm_id,
        )
    ).scalars().first()


def list_irs_authorizations(
    db: Session,
    firm_id: UUID,
    client_id: Optional[UUID] = None,
    form_type: Optional[str] = None,
    status: Optional[str] = None,
) -> list[IrsAuthorization]:
    stmt = select(IrsAuthorization).where(IrsAuthorization.firm_id == firm_id)
    if client_id:
        stmt = stmt.where(IrsAuthorization.client_id == client_id)
    if form_type:
        stmt = stmt.where(IrsAuthorization.form_type == form_type)
    if status:
        stmt = stmt.where(IrsAuthorization.status == status)
    stmt = stmt.order_by(IrsAuthorization.created_at.desc())
    return db.execute(stmt).scalars().all()


def update_irs_authorization(
    db: Session,
    auth: IrsAuthorization,
    auth_in: IrsAuthorizationUpdate,
) -> IrsAuthorization:
    for key, value in auth_in.model_dump(exclude_unset=True).items():
        setattr(auth, key, value)
    db.commit()
    db.refresh(auth)
    return auth


# get_active_authorization_for_client was deleted in Phase F1 Step 8. It
# filtered on status == "active" alone, which is the exact bug Step 8 removed:
# it would hand back an authorization whose valid_until had already passed but
# which the nightly sweep had not yet flipped. Anything needing to know a
# client's authorization situation asks resolve_authorization_state below,
# which reads the date. Do not reintroduce a status-only lookup.


# The five states a form type can resolve to. Deliberately NOT the same
# vocabulary as IrsAuthorization.status:
#
#   - "lapsed" is the reported form of status "expired". The word the product
#     uses to a firm, kept distinct so nobody confuses a resolved state with a
#     row status.
#   - "superseded" has no resolved state at all. A superseded row always had a
#     replacement at the moment it was superseded (see
#     _supersede_prior_active_authorizations, which only ever runs while
#     activating that replacement), so resolution reads the replacement and
#     never reports the retired row.
#
# All five already existed on the model. Nothing here invents a state; this
# stops the two check endpoints collapsing four of them into "none on file",
# which is a false statement to a firm that let an authorization lapse.
AUTH_STATE_ACTIVE = "active"
AUTH_STATE_PENDING = "pending"
AUTH_STATE_LAPSED = "lapsed"
AUTH_STATE_REVOKED = "revoked"
AUTH_STATE_NONE = "none"


# Best to worst. For callers that must collapse two form types into a single
# summary value. The badge in IrsAuthBadge.tsx reads the same ladder in the
# other direction, because it shows the worst case rather than the best.
AUTH_STATE_PRECEDENCE_BEST_FIRST = (
    AUTH_STATE_ACTIVE,
    AUTH_STATE_PENDING,
    AUTH_STATE_REVOKED,
    AUTH_STATE_LAPSED,
    AUTH_STATE_NONE,
)


def _is_past_its_date(row: IrsAuthorization, as_of: date) -> bool:
    """
    Whether this row's own end date has passed, independent of what its status
    column says.

    A null valid_until never lapses. An 8821 with no end date is normal and
    valid indefinitely, and guessing an expiry for it would be inventing a
    fact.

    Strictly less than, and as_of comes from compute_expiry_cutoff_date, so
    this is the identical test get_lapsed_active_authorizations applies in
    SQL. The two must agree to the day: if resolution used <= or a different
    anchor, the badge and the nightly sweep would contradict each other on the
    boundary date, which is the exact class of contradiction this phase exists
    to remove. A row expiring exactly on the cutoff is still valid to both,
    and the sweep treats it as a day-zero warning rather than a lapse.
    """
    return row.valid_until is not None and row.valid_until < as_of


@dataclass(frozen=True)
class ResolvedAuthorizationState:
    """
    What one form type actually amounts to for one client, right now.

    record is the row the state was read off, and is None only when the state
    is "none". expires_on is that row's valid_until and may be None even when
    a record exists: an 8821 with no end date is normal, and a lapsed record
    with no valid_until is reported as a lapse with no date rather than having
    a date guessed for it.
    """
    state: str
    record: Optional[IrsAuthorization] = None
    expires_on: Optional[date] = None


def resolve_authorization_state(
    db: Session,
    firm_id: UUID,
    client_id: UUID,
    form_type: str,
) -> ResolvedAuthorizationState:
    """
    The single source of truth for "what is this client's Form 8821 (or 2848)
    situation". Both check endpoints and the transcript gate answer from here.

    Resolution order, applied in exactly this sequence:

      1. Any "active" row whose valid_until has not passed wins outright.
      2. Otherwise any "pending_signature" row.
      3. Otherwise, if the most recent row that is not superseded is
         "revoked".
      4. Otherwise, if any row has lapsed, that is a lapse, carrying that
         row's valid_until as the expiry date. A row has lapsed if its status
         is "expired" OR if it is still marked "active" but its date has
         passed.
      5. Otherwise no record has ever existed for this form type.

    THE DATE IS AUTHORITATIVE, NOT THE STATUS COLUMN. status only becomes
    "expired" when the nightly sweep runs and flips it. Between the moment an
    authorization actually expires and the moment the sweep reaches it, the
    row still reads "active". Resolving off the column there shows a green
    "IRS Auth: Active" badge and opens the transcript gate on a dead
    authorization. That false green is worse than the false red this phase was
    built to remove, because it invites the firm to act on authority it does
    not hold. The column is a nightly opinion about the date. The date is the
    fact. Do not "fix" this back to reading status alone.

    This is a read and only a read. It never writes, never flips a status
    column and never fires a background job. The nightly sweep still owns the
    write, because two systems writing the same column is how they drift.

    pending_signature is deliberately untouched by the date test. A pending
    authorization has not started, so its end date is not yet meaningful.

    Order matters, and it is not the same as recency. A client who let an 8821
    lapse and has since signed a new one holds an active authorization, so the
    active row wins even though the expired row may be newer in some
    pathological ordering. Equally, a pending renewal does not un-lapse the
    old record, so "active" is checked before "pending".

    Rows are ordered most recent first, so each pass returns the newest row
    matching it.

    A form type whose only rows are superseded falls through to "none". That
    is not reachable today: supersession happens only while a replacement is
    being activated, so a superseded row always has a live sibling.

    Scoped to firm_id. This is per-client state read on a request path, so
    the nightly sweep exemption that applies to
    get_authorizations_in_warning_window does NOT apply here.
    """
    rows = db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.firm_id == firm_id,
            IrsAuthorization.client_id == client_id,
            IrsAuthorization.form_type == form_type,
        ).order_by(IrsAuthorization.created_at.desc())
    ).scalars().all()

    if not rows:
        return ResolvedAuthorizationState(AUTH_STATE_NONE)

    # The same anchor the expiry sweep uses, read once so every pass below
    # judges every row against one calendar date. Never date.today().
    as_of = compute_expiry_cutoff_date()

    for row in rows:
        if row.status == "active" and not _is_past_its_date(row, as_of):
            return ResolvedAuthorizationState(AUTH_STATE_ACTIVE, row, row.valid_until)

    for row in rows:
        if row.status == "pending_signature":
            return ResolvedAuthorizationState(AUTH_STATE_PENDING, row, row.valid_until)

    # Revocation is only the answer if it is the firm's latest word on this
    # form type. A revoked row sitting behind a later expired one is history.
    live = [row for row in rows if row.status != "superseded"]
    if live and live[0].status == "revoked":
        return ResolvedAuthorizationState(AUTH_STATE_REVOKED, live[0], live[0].valid_until)

    # A row still marked "active" that reached this pass is one the sweep has
    # not caught up with yet. It is reported as the lapse it is, carrying its
    # own valid_until. Falling through to "none" instead would tell a firm
    # holding a real record that nothing is on file, which is the other lie
    # this phase exists to stop.
    for row in rows:
        if row.status == "expired" or (
            row.status == "active" and _is_past_its_date(row, as_of)
        ):
            return ResolvedAuthorizationState(AUTH_STATE_LAPSED, row, row.valid_until)

    return ResolvedAuthorizationState(AUTH_STATE_NONE)


# Placeholder until Firm carries a timezone. American Samoa at UTC-11
# is a known, accepted gap.
WESTERNMOST_US_UTC_OFFSET_HOURS = 10


def compute_expiry_cutoff_date() -> date:
    """
    The calendar date the expiry sweep should treat as "today".

    The server runs on UTC. Every US firm is behind it, so for part of each
    UTC day the server's calendar date is already ahead of the firm's. Using
    the raw UTC date would mark an authorization expired while it is still
    valid where the firm actually is, and status = "expired" does not revert.

    Rolling back to the westernmost US offset gives the last calendar date
    that has arrived for every firm in the ICP. This is not the one-day
    safety margin rejected during design: that delayed expiry a full day for
    everyone. This delays it by at most ten hours and produces the identical
    result to the scheduled run time for a firm in any US zone. The
    difference is that it also holds when the sweep is triggered manually at
    four in the morning.

    Correctness lives here rather than in the schedule. See the callers in
    check_expiring_authorizations: the SAME value must reach both queries.
    """
    return (
        datetime.now(timezone.utc)
        - timedelta(hours=WESTERNMOST_US_UTC_OFFSET_HOURS)
    ).date()


def get_authorizations_in_warning_window(
    db: Session,
    max_days: int,
    as_of: date,
) -> list[IrsAuthorization]:
    """
    Active authorizations that have not yet lapsed but expire within
    max_days. This is the set the warning ladder walks.

    as_of comes from compute_expiry_cutoff_date and must be the same value
    passed to get_lapsed_active_authorizations on the same run. If the two
    disagree, an authorization expiring on the boundary date falls into
    neither set and is silently skipped, which is the exact class of
    invisible row this feature exists to eliminate.

    CROSS-FIRM BY DESIGN. This function takes no firm_id and must not be
    given one. It backs the nightly sweep, which runs once for the whole
    installation rather than once per firm, so it relies on the nightly
    sweep exemption to the tenant isolation rule. Scoping it to a single
    firm would silently stop expiry warnings for every other firm. The
    function it replaced, get_authorizations_expiring_soon, relied on the
    same exemption.

    Notification state is deliberately not filtered here. Which tiers have
    already fired lives in irs_authorization_warnings, and the sweep checks
    it per tier.
    """
    window_end = as_of + timedelta(days=max_days)
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.status == "active",
            IrsAuthorization.valid_until.isnot(None),
            IrsAuthorization.valid_until >= as_of,
            IrsAuthorization.valid_until <= window_end,
        )
    ).scalars().all()


def get_lapsed_active_authorizations(
    db: Session,
    as_of: date,
) -> list[IrsAuthorization]:
    """
    Authorizations still marked active whose valid_until is already past
    as_of. These are the ones that slipped through, including any that
    lapsed months ago and were never picked up.

    as_of comes from compute_expiry_cutoff_date and must be the same value
    passed to get_authorizations_in_warning_window on the same run. See the
    note there about boundary rows falling into neither set.

    CROSS-FIRM BY DESIGN. Same nightly sweep exemption as
    get_authorizations_in_warning_window above. Do not add a firm_id
    parameter to this function.

    NO SAFETY MARGIN BEYOND THE CUTOFF, ON PURPOSE. Do not change this to
    valid_until < as_of - timedelta(days=1). The deadline sweep in
    deadline_scheduler.py does subtract a day, and it is right to, because
    its failure mode is a false alarm. This one is inverted. A margin would
    leave a lapsed authorization carrying status = "active" for a further
    full day. Blocking a firm a few hours early is an annoyance. Permitting a
    transcript pull against a dead 8821 tells a firm it holds authority it
    does not hold, on the one surface where being wrong carries legal weight
    for them.

    A margin here no longer reaches the transcript gate, because
    resolve_authorization_state reads valid_until directly against this same
    anchor rather than trusting the column. It would still put a wrong status
    on the row, and it would put this query and _is_past_its_date a day apart,
    so the rule stands.

    The timezone exposure is already handled by as_of. It is NOT handled by
    the schedule: the add_job call in app/main.py picks an hour so that
    warnings arrive before anyone sits down, which is a UX decision. Running
    this sweep off schedule must be, and is, equally correct.

    This query drains itself: the sweep writes status = "expired" for
    everything it returns, so a given row is only ever seen once.
    """
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.status == "active",
            IrsAuthorization.valid_until.isnot(None),
            IrsAuthorization.valid_until < as_of,
        )
    ).scalars().all()
