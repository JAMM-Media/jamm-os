// frontend/src/components/settings/pricing/chain.ts
//
// Shaping only, no rendering and no rules. This module turns the flat merged
// config read into the parent/child chains the complexity section draws.
//
// WHAT IT DELIBERATELY DOES NOT DO. It does not decide whether a scoped
// override beats a blanket config, it does not decide whether a price is
// allowed, and it does not filter anything the server chose to send. Those are
// service decisions with one voice, and a second copy here would drift from
// them. The one system rule mirrored anywhere in this section is the Other
// option key, and that is mirrored to RENDER a refusal the server already
// owns, never to make one.
//
// NOTHING HERE TOUCHES A PRICE. Prices are carried through as number | null
// exactly as they arrived. There is no ?? 0 in this file and there must never
// be one: null means unpriced and routes to quote, 0 means priced at zero.

import {
  OTHER_OPTION_KEY,
  type ComplexityDimension,
  type ComplexityDimensionUnit,
  type ComplexityFlag,
  type ComplexityVocabularyOption,
  type FirmDimensionConfig,
  type FirmOptionPrice,
  type FirmTier,
  type PricingConfig,
} from '@/lib/api/pricing'

export interface TierSlot {
  tier: FirmTier
  // Configs hanging under this tier. A non-empty list is what makes the tier a
  // cleared parent: prices live only at the leaf of a chain, so a tier with
  // children carries no price of its own.
  children: ChainNode[]
}

export interface OptionSlot {
  option: ComplexityVocabularyOption
  // The price ROW for this option in this chain's scope, or null when the firm
  // has never set one. A row that exists with price null is a different thing
  // from no row at all, and both are different from a row priced 0. All three
  // survive to the renderer rather than being flattened here.
  priceRow: FirmOptionPrice | null
  // Rule 9. See OTHER_OPTION_KEY in the typed client.
  isOther: boolean
  children: ChainNode[]
}

export interface ChainNode {
  config: FirmDimensionConfig
  dimension: ComplexityDimension
  flag: ComplexityFlag | null
  // numeric_range only. Null when the dimension is not numeric, and also when
  // the unit the config counted in has since left the catalog: unit_id is
  // ON DELETE SET NULL, so a config outlives its unit.
  unit: ComplexityDimensionUnit | null
  tierSlots: TierSlot[]
  optionSlots: OptionSlot[]
}

export interface ServiceComplexityView {
  // Applies to this service through the system catalog's flag map, alongside
  // every other service that map links.
  blanket: ChainNode[]
  // Attached to this one service's catalog entry.
  scoped: ChainNode[]
  // Configs in this working set that no chain reached: their parent tier or
  // parent option is not among the configs shown here. Rendered rather than
  // dropped, because a row silently missing from a fee schedule screen is the
  // exact shape of failure this repo keeps finding.
  unattached: ChainNode[]
  // Configs naming a dimension the catalog read did not carry. Counted, not
  // guessed at.
  unknownDimensionCount: number
  isEmpty: boolean
}

function groupBy<T>(rows: T[], key: (row: T) => string): Map<string, T[]> {
  const out = new Map<string, T[]>()
  for (const row of rows) {
    const k = key(row)
    const existing = out.get(k)
    if (existing) existing.push(row)
    else out.set(k, [row])
  }
  return out
}

/**
 * Every config this firm has that bears on one engagement type, shaped into
 * chains.
 *
 * entryId is the firm's service catalog entry for this engagement type, or
 * null when the firm has never touched the service. Rows are created lazily,
 * so null is an ordinary state and simply means there can be no scoped
 * override yet.
 */
export function buildServiceComplexityView(
  data: PricingConfig,
  engagementType: string,
  entryId: string | null
): ServiceComplexityView {
  const dimensionsById = new Map(data.dimensions.map((d) => [d.id, d]))
  const flagsById = new Map(data.flags.map((f) => [f.id, f]))
  const unitsById = new Map(data.dimensionUnits.map((u) => [u.id, u]))
  const optionsByDimension = groupBy(data.vocabularyOptions, (o) => o.dimensionId)
  const tiersByConfig = groupBy(data.tiers, (t) => t.configId)

  const flagAppliesHere = (flagId: string): boolean =>
    data.flagEngagementTypes.some(
      (fe) => fe.flagId === flagId && fe.engagementType === engagementType
    )

  // The working set: blanket configs whose flag the catalog maps to this
  // engagement type, plus configs scoped to this service's own entry.
  const inScope: FirmDimensionConfig[] = []
  let unknownDimensionCount = 0
  for (const config of data.configs) {
    const dimension = dimensionsById.get(config.dimensionId)
    if (!dimension) {
      unknownDimensionCount += 1
      continue
    }
    if (config.serviceCatalogEntryId === null) {
      if (flagAppliesHere(dimension.flagId)) inScope.push(config)
      continue
    }
    if (entryId !== null && config.serviceCatalogEntryId === entryId) inScope.push(config)
  }

  const claimed = new Set<string>()

  const buildNode = (config: FirmDimensionConfig): ChainNode => {
    claimed.add(config.id)
    const dimension = dimensionsById.get(config.dimensionId) as ComplexityDimension
    const flag = flagsById.get(dimension.flagId) ?? null
    const unit = config.unitId === null ? null : unitsById.get(config.unitId) ?? null

    const tierSlots: TierSlot[] = (tiersByConfig.get(config.id) ?? [])
      .slice()
      .sort((a, b) => a.sortOrder - b.sortOrder)
      .map((tier) => ({
        tier,
        children: inScope
          .filter((c) => c.parentTierId === tier.id && !claimed.has(c.id))
          .map(buildNode),
      }))

    // A child under a vocabulary option references the OPTION, which belongs to
    // the system dimension rather than to any one config of it. Scope is what
    // separates a blanket child from a scoped one under the same option, and
    // rule 11 (scope is uniform within a tree) is what makes that separation
    // exact.
    const optionSlots: OptionSlot[] = (optionsByDimension.get(dimension.id) ?? []).map(
      (option) => ({
        option,
        priceRow:
          data.optionPrices.find(
            (p) =>
              p.optionId === option.id &&
              p.serviceCatalogEntryId === config.serviceCatalogEntryId
          ) ?? null,
        isOther: option.key === OTHER_OPTION_KEY,
        children: inScope
          .filter(
            (c) =>
              c.parentOptionId === option.id &&
              c.serviceCatalogEntryId === config.serviceCatalogEntryId &&
              !claimed.has(c.id)
          )
          .map(buildNode),
      })
    )

    return { config, dimension, flag, unit, tierSlots, optionSlots }
  }

  const roots = inScope.filter((c) => c.parentTierId === null && c.parentOptionId === null)
  const nodes = roots.map(buildNode)

  const blanket = nodes.filter((n) => n.config.serviceCatalogEntryId === null)
  const scoped = nodes.filter((n) => n.config.serviceCatalogEntryId !== null)
  // Claimed is checked one config at a time rather than filtered up front:
  // building an unattached node claims its whole subtree, and a subtree member
  // collected by an eager filter would then render twice, once nested and once
  // as its own root.
  const unattached: ChainNode[] = []
  for (const config of inScope) {
    if (!claimed.has(config.id)) unattached.push(buildNode(config))
  }

  return {
    blanket,
    scoped,
    unattached,
    unknownDimensionCount,
    isEmpty:
      blanket.length === 0 &&
      scoped.length === 0 &&
      unattached.length === 0 &&
      unknownDimensionCount === 0,
  }
}
