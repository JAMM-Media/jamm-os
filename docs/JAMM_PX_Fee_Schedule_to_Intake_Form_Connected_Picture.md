# JAMM PX: Fee Schedule to Intake Form, the Connected Picture

**Audience:** Ben (and Ben's coding agent), for the intake form phase and everything downstream of it.
**Date:** August 17, 2026.
**Status of everything in this document:** settled and shipped unless a section is explicitly marked RULED, NOT YET BUILT or OPEN. Where a date appears, it is the date the decision was ruled or the code landed.
**Verified against:** the live codebase snapshot of August 17, post-push, migration head 291581aa9ba0. Nothing below is remembered from conversation; every claim was checked against the code.

---

## 1. The one-sentence answer to "how are the questions dynamic"

The intake form contains zero pricing or applicability logic. It renders whatever one GET request returns, and the backend derives that response entirely from what the firm configured in its fee schedule. Dynamic means per-firm and per-service, decided server-side at request time. It does not mean mid-form branching: the question list for a service is flat, known the moment the lead picks a service, and never changes based on their answers.

If you remember one rule, make it this one, ruled August 16:

> **Configured means asked. Priced means automated. Two separate gates.**

A question appears on the form because the firm attached a configuration to that dimension. Whether that configuration carries a price is invisible to the form and irrelevant to it. An answer whose configuration has no price routes to quote downstream, and the form never knows or cares.

---

## 2. The two layers of data, and who owns what

Everything the form renders is derived from two groups of tables.

**The system catalog (shared, owned by JAMM, no firm ever writes to it).** Five tables, the August 13 carve-out, carrying no firm_id: complexity_flags, complexity_flag_engagement_types, complexity_dimensions, complexity_dimension_units, complexity_vocabulary_options. This is the universe of what CAN be asked: 40 flags (crypto, rental property, multi-state, and so on), 84 dimensions under them (the actual askable questions), the unit menus for numeric dimensions, and the answer vocabularies for categorical ones. Seeded by scripts/seed_complexity_catalog.py, 536 rows live in dev. The catalog also decides relevance: complexity_flag_engagement_types maps each flag to the engagement types it applies to, so a business-only flag never generates a question on a 1040 service. Identifiers in this catalog are permanent and shared across every firm, which is what makes cross-firm intelligence possible later. Firms cannot invent their own dimensions; the catch-all Other option and the catalog content feedback loop are the designed answers to gaps.

**The firm attachment tables (per-firm, tenant-isolated, written through the pricing settings UI).** service_catalog_entries holds, per firm per engagement type, is_offered plus pricing_mode plus base_fee. Despite the catalog-sounding name it is NOT carve-out content; it carries firm_id and is always queried firm-scoped. firm_dimension_configs is the attachment: one row means "this firm has switched this dimension on," and carries the dimension's role, unit choice, guard threshold, branch position, and (as of August 17) scope. firm_tiers and firm_option_prices hold the actual numbers.

The form is a projection of the intersection: system catalog says what is askable and for which services, firm configuration says what this firm actually asks.

---

## 3. The endpoint your form consumes

**GET /intake/{slug}/pricing-config** exists, is live in the codebase, and is the endpoint your form renders from. Facts about it, all shipped:

- No auth, on purpose (Addendum 1 section 9). Leads are anonymous. It is safe to be public only because of the stripping contract in section 5 below.
- Rate limited 30/minute, more generous than submit's 5/minute because it is a read.
- 404 with the same message and status as the sibling config endpoint, so slugs cannot be enumerated by error shape.
- Not paginated: it is one configuration object, not a list resource.
- No behavioral event fires on this read. Form-view and form-interaction events belong to your intake phase, where lead context exists.

### The response shape (exact, from app/schemas/intake_pricing_config.py)

```
IntakePricingConfigOut
  slug: str
  firm_name: str
  services: list[IntakeServiceOut]        # may be empty; empty is a real state, HTTP 200

IntakeServiceOut
  engagement_type: str                    # canonical stored value; submit this back
  label: str | null                       # lead-facing display string, from ENGAGEMENT_TYPE_LABELS
                                          # in app/core/enums.py, the single source of truth.
                                          # Never hand-maintain a copy of these strings.
  questions: list[IntakeQuestionOut]      # may be empty; an offered service with nothing
                                          # configured still appears, with an empty list

IntakeQuestionOut
  flag_key: str                           # e.g. "crypto"; stable grouping key
  flag_name: str                          # lead-facing flag name
  dimension_key: str                      # stable identifier for the question
  kind: str                               # "boolean" | "categorical" | "numeric_range"
  question_text: str | null               # NULLABLE, see below
  options: list[IntakeQuestionOptionOut]  # populated only for categorical

IntakeQuestionOptionOut
  id: UUID                                # opaque system vocabulary option id; hand it back on submit
  label: str                              # lead-facing answer text
```

### Rendering rules the shape implies

- **Three question kinds, three widgets.** boolean is a yes/no. categorical renders its options list (only active options are ever served; a retired answer is never offered to a lead). numeric_range is a number input whose phrasing comes from the unit the firm configured; one dimension can legitimately produce several numeric questions, one per distinct configured unit, each with its own question_text.
- **question_text can be null and that is deliberate.** The dimension and unit question_text columns are nullable pending the content pass (Lori audits before copy is final). A configured dimension with no text yet is served with a null question rather than dropped, so the gap stays visible to the frontend instead of silently shrinking the form. Render a visible placeholder in dev; do not filter nulls out.
- **Ordering is stable and server-decided:** flag key, then dimension hierarchy_rank, then dimension key, then unit key. Same configuration, same form, every call. Do not re-sort.
- **Empty states are real states, not errors.** A firm offering nothing returns an empty services list with HTTP 200. An offered service with zero configured questions appears with an empty questions list. Render both honestly.

### What the form never sees, and why the questions are flat

Firms can chain dimensions under tiers and options (matrix-within-matrix pricing). None of that structure reaches the form. The service layer deduplicates configs by dimension before building questions: a dimension configured on five branches and one configured flat produce a question of exactly the same shape, once. Ruled in Addendum 2: **chains shape pricing, not question visibility.** So your form asks a flat list per service, and the pricing engine downstream applies the chain logic to the answers. This is why there is no mid-form branching to build, and no way for the response to leak how a firm's pricing is structured.

---

## 4. What the lead's answers mean downstream (context, not your build)

The form collects: the chosen engagement_type value, plus per question either a boolean, a number, or an option id. The option id is the load-bearing one: it is the opaque handle that lets the backend resolve the answer to that firm's price for it later, without the form ever having seen a price.

Resolution follows the **null-versus-zero law**, which is absolute at every layer: a price of NULL means unpriced and routes to quote (a human at the firm looks at it); an explicit 0.00 means priced at zero. They are never coerced into each other. The catch-all Other option on every categorical vocabulary is permanently unpriceable by service guard (rule 9), so an "Other" answer always routes to quote by construction.

The companion principle, ruled August 17: **nothing unconfigured ever dismisses a lead.** An owner can activate an engagement type and configure nothing; every lead for it simply routes to quote. Unconfigured is a legitimate resting state, and the failure mode of missing configuration is always a conversation, never a lost lead and never an invented number. The only thing that can disqualify a lead is an explicit disqualification rule the firm set up, which records the triggering question and answer.

---

## 5. The stripping contract (read this before touching anything near the endpoint)

The endpoint is safe to serve unauthenticated for exactly one reason: every commercial fact is gone before the response leaves the service layer. The following appear nowhere at any depth, and may never be added:

price, base_fee, or any monetary value; pricing_mode; role and guard_threshold; range_min, range_max, sort_order, or any tier data; parent ids or any chain structure; firm_id, config ids, tier ids, timestamps.

The schemas are physically incapable of carrying these (there is deliberately no Decimal import in the schema file), and tests/test_intake_pricing_config.py walks a serialized response recursively and fails on any forbidden key at any depth. That test is the enforcement. If it is ever deleted or weakened, the endpoint stops being safe to serve without auth.

Related trap, documented in the service: **two reads exist side by side with similar names.** get_fee_schedule_config is the OWNER'S view (everything, blanket and scoped, priced, for the settings UI, firm_owner auth). get_public_intake_config is the stripped public twin. Wiring a public surface to the owner view would expose every engagement type's pricing to anonymous visitors. Both docstrings carry warnings; keep it that way.

---

## 6. What changed this week: per-engagement-type overrides (the pivot to absorb)

Ruled and built August 17. A firm can now configure the same catalog dimension differently per engagement type. Crypto on a 1040 and crypto on an 1120 can carry different structures and different prices, while remaining the same catalog dimension with the same shared identifiers (so cross-firm intelligence is unaffected, and arguably deepened).

Mechanics, all shipped and guard-tested (38 new tests, 12 negative controls, all watched red):

- firm_dimension_configs and firm_option_prices both carry a nullable service_catalog_entry_id. NULL means blanket (applies to every engagement type the flag maps to). Non-NULL means the row applies only when pricing that engagement type.
- **Precedence is wholesale replacement, never a field-level merge.** If a scoped tree exists for (dimension, engagement type), it entirely supplies the configuration; the blanket tree is not consulted at all.
- **No fallback exists in any form.** Inside a winning scoped tree, an option with a cleared price and an option with no scoped price row behave identically: both are unpriced, both route to quote. Neither borrows the blanket price. (The settings UI mitigates by prefilling a new override from blanket values at creation; that is a copy at creation time, not a merge at resolution time, and it is the UI's job, not the resolver's.)
- Scope is uniform within a tree, immutable after creation, and tenant-isolated (a firm cannot scope to another firm's catalog entry; the refusal is a 404 so catalog entries cannot be enumerated).
- resolve_pricing_config(db, firm_id=..., engagement_type=...) is the new resolution entry point: one answer per dimension, precedence applied. This is what fee resolution consumes.

### What this means for the intake form. RULED, NOT YET BUILT.

Today, GET /intake/{slug}/pricing-config ignores scope: it was written before the override work, so a dimension the firm configured ONLY as (say) a 1040 override currently surfaces as a question on every service its flag maps to. The ruled behavior (August 17) is that applicability becomes scope-aware per service: for each service, a question exists if the firm has a config for that dimension that applies to that service, meaning a blanket config or a config scoped to it. A dimension configured only as a 1040 override will produce its question only under the 1040 service.

**The response shape does not change.** Same schemas, same fields, same stripping contract. Only which questions appear inside each service's list gets more precise. If you build the form against the current contract, the scope-awareness pass will change contents, not structure. That pass is the very next backend session on Andrew's side and lands before your intake phase needs it.

---

## 7. The seams reserved for your intake phase (from the contract, unchanged)

For orientation, the pieces that are explicitly yours and already have their seams:

- **The warm path:** nurture email links carry a lead token; the page recognizes the lead; answers prefill; partial progress saves durably. Form events land as rows the nurture engine can branch on; the LeadMessage.source form_reply seam exists for this. Disqualification records which question and which answer.
- **The cold path exists today:** POST /intake/{slug}/submit is live, Turnstile-gated, rate limited 5/minute, and is the one place in the codebase that creates a lead with provenance crm_lead.
- **Branching stays replies-only in v1.** Clicks and bare page visits are scanner-contaminated and are recorded for intelligence but never branched on. The trust ladder: click, then page visit, then form field interaction or partial save, then Turnstile-verified submit.
- **Behavioral events for form views and interactions are yours to fire,** with lead context, in the service layer, fire-and-forget, recorder never gatekeeper.

### Known gap, on the record

IntakeSubmitBody accepts how_did_you_hear but does not persist it: the Lead model has no freeform attribution field yet (referral_source is the structured enum). The code comments note a future attribution_notes column. Also note the current submit body carries no complexity answers at all; where and how question answers persist on submit is part of your intake phase design, against the seams above, and should be agreed with Andrew before you build it.

---

## 8. Open items that touch this picture (so nothing here surprises you later)

- **Scope-aware applicability on the public endpoint:** ruled, next backend session, contents-only change (section 6).
- **Referral-source required-field decision:** open ruling on Andrew's list; blocks the import wizard's last UX gap and touches your form's field set.
- **Question copy:** question_text fills in during the content session, Lori audits first. Expect nulls until then.
- **Engagement letter and billing:** the snapshot law is locked (letters store structured line items at generation; billing reads the snapshot forever, never the live fee schedule), so nothing you build against the fee schedule ever needs billing hooks.
- **Pricing of JAMM itself** (subscriptions) is a separate, undecided topic and has nothing to do with any of this. The firm-facing fee schedule inside the product, described here, is locked.

---

## 9. The five-sentence version, for when someone asks

The system catalog defines everything askable and which engagement types it applies to. A firm switches questions on by configuring dimensions in its fee schedule, and prices them there too, but those are two separate acts: configured means asked, priced means automated. The public intake endpoint projects that configuration into a flat, price-stripped question list per offered service, and the form renders it with no logic of its own. Answers travel back as opaque option ids and numbers, and anything the firm has not priced routes to a human quote instead of being guessed or dismissed. As of this week the same dimension can be configured differently per engagement type, with the scoped version wholly replacing the blanket one whenever it exists.
