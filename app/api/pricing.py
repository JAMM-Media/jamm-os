# app/api/pricing.py

"""Config surface for the pricing service, read and write.

GET /config was this router's first endpoint and the access rules are stated
on it in full rather than inherited from a neighbouring router. The six write
endpoints below were added afterwards and adopt those same rules verbatim:
require_firm_owner, deliberately, for the reason spelled out on the read.

EVERY ENDPOINT HERE IS THIN. Authenticate, check the role, call the service,
return what it returns. No query logic and no business rules live in this file.
Every guard that can refuse one of these calls lives in
pricing_config_service, raises HTTPException itself, and its message reaches
the client unaltered, because the settings UI renders refusal detail verbatim
rather than replacing it with generic copy.

NOTHING HERE IS PAGINATED, ON PURPOSE, NOT AS AN OVERSIGHT. The standing rule
that list endpoints use PaginatedResponse[T] governs endpoints returning a
list of independent objects. None of these do. See the note on the tier
endpoint, which is the only one that returns a JSON array at all.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.models.firm import Firm
from app.models.user import User
from app.dependencies.tenant import get_current_firm
from app.schemas.fee_schedule_config import FeeScheduleConfigOut
from app.schemas.firm_dimension_config import (
    ConfigMoveRequest,
    FirmDimensionConfigCreate,
    FirmDimensionConfigOut,
)
from app.schemas.firm_option_price import FirmOptionPriceCreate, FirmOptionPriceOut
from app.schemas.firm_tier import FirmTierBase, FirmTierOut
from app.schemas.service_catalog_entry import (
    ServiceCatalogEntryCreate,
    ServiceCatalogEntryOut,
)
from app.services import pricing_config_service

router = APIRouter(prefix="/api/pricing", tags=["Pricing"])


@router.get("/config", response_model=FeeScheduleConfigOut)
def get_fee_schedule_config(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    # RBAC: firm_owner only, ON PURPOSE, NOT AS AN OVERSIGHT.
    #
    # require_firm_owner admits firm_owner and system_admin. Manager and staff
    # are refused 403. That is deliberately stricter than most read endpoints
    # in this codebase because a fee schedule is the firm's commercial core.
    #
    # A firm-owner-configurable per-role read/edit permissions setting is a
    # real planned item and would let an owner open this up to managers. It
    # touches several areas of the build, not just this endpoint, and belongs
    # in its own settings-tab session. Until that ships, do not widen this to
    # require_manager_or_above and do not add a local toggle here.
    _: User = Depends(require_firm_owner),
):
    """The merged fee schedule for the calling firm.

    NOT PAGINATED, ON PURPOSE, NOT AS AN OVERSIGHT. The standing rule that all
    list endpoints use PaginatedResponse[T] applies to endpoints that return a
    list. This one returns a single config object. Its interior collections are
    the parts of one indivisible whole: a paged catalog with unpaged firm
    pricing (or the reverse) would describe a fee schedule that does not exist,
    and the caller is a settings screen that needs the entire thing at once to
    render anything at all.

    Thin by construction: authenticate, check the role, call the service, return
    what it returns. No query logic lives here.
    """
    return pricing_config_service.get_fee_schedule_config(db, firm_id=current_firm.id)


# ---------------------------------------------------------------------------
# Write endpoints.
#
# RBAC on every one of them is require_firm_owner, ON PURPOSE, NOT AS AN
# OVERSIGHT, and for exactly the reason given at length on GET /config above:
# a fee schedule is the firm's commercial core. These are the endpoints that
# CHANGE it, so if anything the case is stronger here than on the read. The
# same deferred firm-owner-configurable per-role permissions session that will
# revisit the read will revisit these. Until it ships, do not widen any of
# these to require_manager_or_above and do not add a local toggle.
# ---------------------------------------------------------------------------


@router.put("/catalog/{engagement_type}", response_model=ServiceCatalogEntryOut)
def upsert_catalog_entry(
    engagement_type: str,
    data: ServiceCatalogEntryCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    """Create or update this firm's catalog entry for one engagement type.

    PUT rather than POST because the operation is an upsert addressed by a
    natural key: one firm has at most one entry per engagement type, and
    calling this twice with the same body leaves the same single row.

    The engagement_type appears in the path AND in the body. They must agree.
    Rejecting the mismatch is the router's own job rather than the service's,
    because the service never sees the path: it is handed one object and has no
    way to know what URL it arrived on. This is the one piece of validation in
    this file, and it exists because the alternative is silently trusting one
    of the two and writing to an address the caller did not name.
    """
    if data.engagement_type != engagement_type:
        raise HTTPException(
            status_code=422,
            detail=(
                f"engagement_type in the body ('{data.engagement_type}') does "
                f"not match the path ('{engagement_type}'). They address the "
                "same entry and must agree."
            ),
        )
    return pricing_config_service.upsert_service_catalog_entry(
        db, firm_id=current_firm.id, actor_id=current_user.id, data=data
    )


@router.post("/configs", response_model=FirmDimensionConfigOut, status_code=201)
def create_dimension_config(
    data: FirmDimensionConfigCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    """Attach one system complexity dimension to this firm.

    201 because this creates a new row at a new identity every time. It is not
    an upsert: a firm may configure the same dimension more than once, blanket
    and scoped, and those are different configs rather than one being an edit
    of the other.
    """
    return pricing_config_service.configure_dimension(
        db, firm_id=current_firm.id, actor_id=current_user.id, data=data
    )


@router.put("/configs/{config_id}/tiers", response_model=list[FirmTierOut])
def save_config_tiers(
    config_id: uuid.UUID,
    tiers: list[FirmTierBase],
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    """Replace the complete tier set for one config.

    NOT PAGINATED, ON PURPOSE, NOT AS AN OVERSIGHT. This is the only endpoint
    in this file that returns a JSON array, so it is the only one where the
    standing PaginatedResponse[T] rule could even be mistaken for applying.
    It does not. These tiers are not independent objects that happen to share a
    page: they are the complete, ordered set belonging to one config, and they
    are one indivisible whole. The tier sequence rules that validate them
    (contiguity, ordering, the single open top) are properties of the SET, so
    a half of it is not a smaller valid answer, it is a different and invalid
    one. A caller holding page one of a tier ladder holds something that does
    not describe any real fee schedule.

    PUT and not PATCH: the body is the entire new set, and tiers absent from it
    are removed. save_tiers matches incoming tiers to existing ones by
    sort_order and updates in place rather than deleting and recreating, for
    the data-corruption reason written out at length in its docstring.
    """
    return pricing_config_service.save_tiers(
        db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        config_id=config_id,
        tiers=tiers,
    )


@router.put("/option-prices", response_model=FirmOptionPriceOut)
def set_categorical_option_price(
    data: FirmOptionPriceCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    """Set or clear this firm's price on one categorical option, in one scope.

    PUT for the same reason as the catalog entry: an upsert addressed by a
    natural key, here (firm, option, scope).

    THE NULL-VERSUS-ZERO LAW PASSES THROUGH THIS ENDPOINT UNTOUCHED. A body
    carrying price null and a body carrying price 0.00 are two different
    requests and stay different all the way down: null means unpriced and
    routes to quote, 0.00 means priced at zero. This router does no coercion,
    no "or 0", and supplies no default, so there is nothing here that could
    collapse them. Note also that the two nullable fields in this body are
    unrelated: price null is about money, service_catalog_entry_id null means
    blanket scope.
    """
    return pricing_config_service.set_option_price(
        db, firm_id=current_firm.id, actor_id=current_user.id, data=data
    )


@router.post("/configs/{config_id}/move", response_model=FirmDimensionConfigOut)
def move_dimension_config(
    config_id: uuid.UUID,
    data: ConfigMoveRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    """Move a config between branches, or between flat and dependent.

    POST rather than PUT or PATCH: this is a named destructive action, not an
    edit of a representation. Every price belonging to the moved config and
    everything below it is deleted, because those prices stop meaning what they
    meant the moment the chain above them changes.

    confirm lives in the BODY here, unlike the delete below where it is a query
    parameter. The difference is not an inconsistency: this endpoint already
    has a body it cannot do without, and the delete has none, since DELETE
    bodies are poorly supported across clients and proxies.

    Scope is not changeable here and there is deliberately no re-scope
    operation anywhere in this build. See change_dimension_direction.
    """
    return pricing_config_service.change_dimension_direction(
        db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        config_id=config_id,
        new_parent_tier_id=data.new_parent_tier_id,
        new_parent_option_id=data.new_parent_option_id,
        confirm=data.confirm,
    )


@router.delete("/configs/{config_id}", status_code=204)
def delete_dimension_config(
    config_id: uuid.UUID,
    confirm: bool = Query(
        False,
        description=(
            "Must be true to proceed. Without it the call is refused with a "
            "422 naming exactly what would be destroyed."
        ),
    ),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    """Delete one config, everything below it, and every price they carry.

    confirm is a QUERY PARAMETER rather than a body field because DELETE
    bodies are poorly supported by clients, proxies and caches, and a
    confirmation flag that some layer is free to drop is worse than no flag.

    204 and no body on success. There is nothing meaningful to return: the
    thing the caller would name is gone.

    THE REFUSAL PATH IS ASYMMETRIC BETWEEN FIRMS, AND THAT IS THE RATIFIED
    BEHAVIOUR, NOT AN INCONSISTENCY. delete_config loads the config before it
    looks at confirm, so a caller naming a config that does not exist or that
    belongs to another firm gets 404 from the lookup no matter what confirm
    says. Only the owning firm ever reaches the 422, whose message names the
    dimension and counts what would be destroyed. Checking confirm first would
    have handed that census to anyone who guessed a UUID, which is a
    cross-firm existence and blast-radius leak. Do not reorder this to match
    change_dimension_direction, whose confirm check does come first precisely
    because its refusal message is generic and names nothing.
    """
    pricing_config_service.delete_config(
        db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        config_id=config_id,
        confirm=confirm,
    )
    return Response(status_code=204)
