# Metric Clock Definitions - Locked July 2026

These definitions were locked in a design session outside the repo and are
reproduced here verbatim as the permanent, authoritative reference. They are
permanent once historical summaries are computed against them. Registry keys
are in parentheses.

## METRIC 1 - ENGAGEMENT VELOCITY (engagement_velocity)

Question: How long does it take this firm to get a unit of billable work done?

- Clock start: engagement creation. Creation-to-first-activity lag is real
  firm behavior and belongs in the number.
- Clock stop: final status change to completed.
- Reopened engagements: the clock extends to the final completion. The
  original completion event is preserved in the stream; the metric value
  is recomputed on reopen.
- Benchmark-eligible: yes.

## METRIC 2 - DEADLINE ADHERENCE (deadline_adherence_original, deadline_adherence_extended, deadline_adherence_operative)

Question: Does this firm hit its filing deadlines?

Three tracks recorded per deadline-carrying engagement:

1. Beat original deadline - yes/no.
2. Beat extended deadline - yes/no, only where an extension exists.
3. Beat operative deadline - completed before whichever deadline was in
   force (extended if extended, original otherwise). Lower importance
   weight than tracks 1-2; weighting lives in the severity/display layer.

- Miss recognition: an engagement becomes non-adherent the moment its
  operative deadline passes without completion, recorded against every
  track it failed. Misses are never deferred to eventual completion.
- Scope: filing and extension deadlines only (the firm-independent anchor;
  the IRS sets them).
- Extension timing is NOT folded into adherence; it lives in the separately
  captured extension.filed timing distribution.
- Benchmark-eligible: yes, all three tracks.
- Companion metric: Internal Due-Date Adherence - same three-track
  computation over internal due dates, firm-facing only, never
  benchmark-eligible (internal dates are self-set and self-movable).
  Not yet in the registry; register at a later authoring session.

## METRIC 3 - DOCUMENT COLLECTION SPEED (document_collection_speed)

Question: When this firm asks a client for documents, how long until it
has everything it needs?

- Clock start: document request sent. (Open-tracking is unreliable
  plumbing; prompting clients to engage is part of collection performance.)
- Clock stop: the last upload of an item actually used. Waive timestamps
  never extend the duration - the firm had what it needed at the final
  upload; the waive is retroactive recognition, not a collection event.
- All-waived requests (nothing ever uploaded): count as completed for
  completion-rate purposes, contribute no duration observation.
- Abandoned requests (partial upload, never completed): resolve as
  non-completions when the engagement completes or is archived.
  Contribute to completion rate, no duration observation.
- Benchmark-eligible: yes.

## METRIC 4 - INVOICE PAYMENT TIME (invoice_payment_time)

Question: When this firm sends an invoice, how long until it is fully paid?

- Clock start: invoice sent.
- Clock stop: zero balance (time-to-zero). Partial payments do not stop
  the clock; only full payment does.
- Payment-plan invoices: INCLUDED in the benchmark pool on the same
  time-to-zero basis.
- Installment adherence, refund signals, and write-off rates are
  firm-facing signals only, never cross-compared.
- Benchmark-eligible: yes.

## METRIC 5 - PORTAL UTILIZATION (portal_utilization_documents, portal_utilization_invoices, portal_utilization_todos, portal_utilization_esign)

Question: When there was a concrete thing for a client to do, was the
portal the channel it happened through?

- Per-opportunity, per-type. NO time window, NO activity threshold,
  NO active-client definition. Each opportunity is one observation with
  a firm-independent anchor: the thing existed; where did it get done?
- Launch opportunity set, each its own registered metric:
  document request items (portal upload vs staff upload/outside channel),
  invoice payments (portal vs any other method), todos (portal vs
  resolved otherwise), e-signatures (portal flow vs otherwise).
- Resolution-only scoring: an opportunity produces an observation only
  when it resolves - via portal, via another channel, or by dying with
  the engagement (request never fulfilled but engagement completes =
  documents arrived outside the portal = non-portal resolution).
  Pending work never reads as portal failure.
- Note: the same event can read differently per metric. An orphaned
  document request is a non-completion for collection speed and a
  non-portal resolution for utilization. Different questions, both honest.
- Any headline "portal adoption" number is a display composite over the
  per-type rates, never a metric definition.
- Companion metric: Portal Offer Rate (share of clients ever invited,
  from client.portal_invited). Separate track, not yet registered,
  benchmark eligibility TBD.
- Benchmark-eligible: yes, all four types.

## METRIC 6 - AUTOMATION UTILIZATION (automation_utilization)

Question: How much of the automation power available to this firm is
actually working for it?

- Definition: share of available PRESET automation rules that are enabled
  AND have fired at least once, ever.
- "Ever," not "recently": seasonal rules legitimately sleep for months;
  a recency window would misread healthy firms every off-season.
- Enabled-but-never-fired stays out of the numerator: configuration
  theater is not utilization.
- Versioned denominator: computed against the preset catalog as of the
  observation date. Historical values stay true to their moment; the
  registry entry notes catalog-version sensitivity.
- Custom rules excluded from the benchmark metric (they vary per firm
  by definition and fail the firm-independent-anchor test).
- Benchmark-eligible: yes.

## Clarifications - July 2026

- Document collection "actually used": the clock stops at the last upload
  among items not ultimately waived. A rejected-then-reuploaded item counts
  at its final upload.
- Automation utilization: a catalog slot counts as utilized when a rule with
  that preset_key is enabled and has fired at least once, regardless of
  is_customized. Customization state is stamped in fire metadata for
  analysis but does not affect the metric. Only rules with null preset_key
  (pure customs) are excluded. Lineage (preset_key) is permanent;
  customization is state.
- portal_utilization_todos: deactivated. The portal To-do tab surfaces
  document request items, already counted by portal_utilization_documents.
  Reactivate if and when a standalone Todo entity ships as its own feature.
