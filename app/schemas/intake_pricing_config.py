# app/schemas/intake_pricing_config.py

"""Read-only response schemas for GET /intake/{slug}/pricing-config.

The public, unauthenticated question tree Ben's intake form renders: which
services a firm offers, and for each, the complexity questions that firm has
actually configured. The endpoint contract is CRM Build Contract Addendum 1
section 9, flattened per Addendum 2.

THERE IS NO Base, Create OR Update HERE, DELIBERATELY, for the same reason
app/schemas/fee_schedule_config.py has none. This is a read projection
assembled from seven tables, not a persisted entity, so the standing
four-schema rule has nothing to apply to. Every table behind it already owns
its own schema set and every write continues to go through those. Adding a
Create or Update here would invent a second write path into tables that
already have one, and this one would be reachable without authentication.

THE STRIPPING CONTRACT IS THE POINT OF THIS FILE, NOT A SIDE EFFECT OF IT.
These schemas are what makes the endpoint safe to serve to an anonymous
visitor, so what is ABSENT below is load-bearing. None of the following
appears at any depth, and none of it may ever be added:

    price, base_fee, or any monetary value
    pricing_mode
    role (priced, informational, guard) and guard_threshold
    range_min, range_max, sort_order, or any tier data
    parent_tier_id, parent_option_id, or any chain or hierarchy structure
    firm_id, config row IDs, tier IDs, or timestamps

What survives is the set of facts a lead needs in order to answer a question:
engagement type values, flag keys and names, dimension keys and question text,
unit-generated question text, and vocabulary option IDs with their labels.

THERE IS DELIBERATELY NO Optional[Decimal] IN THIS FILE, AND NO IMPORT OF
Decimal. There is no legitimate monetary field in this response, so the type
has no business existing here. Its absence is the first thing to check if this
file is ever edited.

tests/test_intake_pricing_config.py walks a serialized response recursively and
fails on any forbidden key at any depth. That test is the enforcement; this
docstring is only the explanation.
"""

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IntakeQuestionOptionOut(BaseModel):
    """One selectable answer to a categorical question.

    id is the system-owned complexity_vocabulary_options primary key, served as
    an OPAQUE identifier. It is safe to expose: it belongs to the shared system
    catalog (the August 13, 2026 carve-out), carries no firm_id, and is
    identical for every firm. The intake form hands it back on submit, which is
    what makes the answer resolvable to a price later without the form ever
    having seen one.
    """

    id: uuid.UUID
    label: str

    model_config = ConfigDict(from_attributes=True)


class IntakeQuestionOut(BaseModel):
    """One question the form asks.

    A question exists here only because the firm configured the dimension
    behind it. Whether that configuration carries a price is invisible at this
    layer, by the August 16, 2026 ruling: configured means asked, priced means
    automated, and they are separate gates.

    question_text is Optional because complexity_dimensions.question_text and
    complexity_dimension_units.question_text are both nullable at the model
    layer, pending the content session that fills them. A configured dimension
    with no text yet is served with a null question rather than dropped, so the
    gap is visible to the frontend instead of silently shrinking the form.

    options is empty for boolean and numeric_range questions. It is populated
    only for categorical ones, where it carries that dimension's active system
    vocabulary.

    NOTE ON WHAT IS NOT HERE: there is no config id, no role, no unit id, no
    parent, and no indication of how many times the firm configured this
    dimension or how it is chained. A dimension configured on five branches and
    one configured flat produce a question of exactly the same shape.
    """

    flag_key: str
    flag_name: str
    dimension_key: str
    kind: str
    question_text: Optional[str] = None
    options: list[IntakeQuestionOptionOut] = []


class IntakeServiceOut(BaseModel):
    """One service the firm offers, with its questions.

    engagement_type is the canonical stored value, which is what the intake
    form submits back. label is the formal display string from
    ENGAGEMENT_TYPE_LABELS in app/core/enums.py, the single backend source of
    truth for these strings; it is NOT a hand-copied list maintained here. It
    is Optional only to survive a stored engagement_type that is not an
    EngagementType member, which the schema layer normally prevents.

    lead_facing_label and category are the two PRESENTATION fields added
    August 18, 2026 for the intake form funnel. Both are content-free today on
    purpose: their maps in app/core/enums.py ship empty and are filled by the
    catalog content session. THE SHAPE BELOW IS FINAL REGARDLESS. Filling those
    maps changes what these fields say and never whether they are here, which
    is the whole reason they were added before their content existed.

    lead_facing_label is the plain-English name a lead sees. It NEVER arrives
    null while label is non-null: an engagement type with no LEAD_FACING_LABELS
    entry falls back to its ENGAGEMENT_TYPE_LABELS value, so the form always has
    something to render and never has to implement the fallback itself. Today,
    with the map empty, it equals label for every service.

    category is the broad bucket the form groups this service under, one of
    ServiceCategory (tax, bookkeeping, advisory), serialized as its string
    value. It is genuinely Optional and null is a real, permanent state, not a
    gap waiting to be filled: a type with no ENGAGEMENT_TYPE_CATEGORIES entry
    is uncategorized and the form renders it in a flat, ungrouped list. There
    is deliberately no default bucket.

    NEITHER FIELD IS A COMMERCIAL FACT, which is the only reason they are
    allowed in this file at all. A bucket name and a friendly service name tell
    a lead nothing about what anything costs. The stripping contract in the
    module docstring above is unchanged by their presence, and
    tests/test_intake_pricing_config.py still walks the whole response for
    forbidden keys with both of these in it.

    questions may be empty. An offered service with nothing configured is a
    real state and appears with an empty list, not omitted.
    """

    engagement_type: str
    label: Optional[str] = None
    lead_facing_label: Optional[str] = None
    category: Optional[str] = None
    questions: list[IntakeQuestionOut] = []


class IntakePricingConfigOut(BaseModel):
    """The whole public config for one firm's intake form.

    slug and firm_name are already public: GET /intake/{slug}/config serves
    both to the same anonymous audience today. Nothing is added here beyond
    what that endpoint already exposes.

    services may be empty. A firm offering nothing returns an empty list with
    HTTP 200, because empty is a real state and not an error.
    """

    slug: str
    firm_name: str
    services: list[IntakeServiceOut] = []
