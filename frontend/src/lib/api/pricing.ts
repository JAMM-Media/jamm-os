// frontend/src/lib/api/pricing.ts
//
// The pricing settings API surface: one read and the write endpoints behind it.
//
// THE NULL VERSUS ZERO LAW LIVES IN THESE TYPES. Every price is
// `number | null`, never `number`, and never optional. null means unpriced and
// routes to quote; 0 means priced, at zero. Nothing in this file may default,
// coerce or fill a price, so there is no `?? 0` anywhere below and there must
// never be one. An optional field would let `undefined` in as a third state
// that the backend has no word for.
//
// There is deliberately NO hand-copied engagement type list here. The server
// serves the complete list with its display strings, because five separate
// copied lists already exist in this frontend and have drifted from each other
// and from the backend. The tab this replaces names its own copied list as the
// thing the replacement exists to remove.

import api from '@/lib/api'

export type PricingMode = 'fixed' | 'hourly' | 'range' | 'quote_only'

export interface EngagementTypeOption {
  value: string
  label: string
  leadFacingLabel: string
  category: string | null
}

export interface ServiceCatalogEntry {
  id: string
  firmId: string
  engagementType: string
  isOffered: boolean
  pricingMode: PricingMode | null
  baseFee: number | null
}

export interface ComplexityDimension {
  id: string
  flagId: string
  key: string
  kind: string
  hierarchyRank: number
  linkable: boolean
  defaultRole: string | null
}

export interface FirmDimensionConfig {
  id: string
  firmId: string
  dimensionId: string
  serviceCatalogEntryId: string | null
  parentTierId: string | null
  parentOptionId: string | null
  role: string
  unitId: string | null
  guardThreshold: number | null
}

export interface FirmTier {
  id: string
  configId: string
  rangeMin: number
  rangeMax: number | null
  price: number | null
  sortOrder: number
}

export interface FirmOptionPrice {
  id: string
  optionId: string
  serviceCatalogEntryId: string | null
  price: number | null
}

export interface PricingConfig {
  firmId: string
  engagementTypes: EngagementTypeOption[]
  serviceCatalogEntries: ServiceCatalogEntry[]
  dimensions: ComplexityDimension[]
  configs: FirmDimensionConfig[]
  tiers: FirmTier[]
  optionPrices: FirmOptionPrice[]
}

// Money arrives as a JSON string or number from Decimal columns. null must
// survive as null: Number(null) is 0, which would silently turn "unpriced"
// into "free" and is exactly the collapse the law forbids.
function money(value: unknown): number | null {
  if (value === null || value === undefined) return null
  const n = Number(value)
  return Number.isNaN(n) ? null : n
}

export function mapPricingConfig(raw: Record<string, unknown>): PricingConfig {
  const catalog = (raw.catalog ?? {}) as Record<string, unknown>
  const firmPricing = (raw.firm_pricing ?? {}) as Record<string, unknown>

  return {
    firmId: String(raw.firm_id ?? ''),
    engagementTypes: ((catalog.engagement_types ?? []) as Record<string, unknown>[]).map(
      (e) => ({
        value: String(e.value),
        label: String(e.label),
        leadFacingLabel: String(e.lead_facing_label),
        category: e.category === null || e.category === undefined ? null : String(e.category),
      })
    ),
    serviceCatalogEntries: (
      (catalog.service_catalog_entries ?? []) as Record<string, unknown>[]
    ).map((e) => ({
      id: String(e.id),
      firmId: String(e.firm_id),
      engagementType: String(e.engagement_type),
      isOffered: Boolean(e.is_offered),
      pricingMode: (e.pricing_mode ?? null) as PricingMode | null,
      baseFee: money(e.base_fee),
    })),
    dimensions: ((catalog.complexity_dimensions ?? []) as Record<string, unknown>[]).map(
      (d) => ({
        id: String(d.id),
        flagId: String(d.flag_id),
        key: String(d.key),
        kind: String(d.kind),
        hierarchyRank: Number(d.hierarchy_rank),
        linkable: Boolean(d.linkable),
        defaultRole: d.default_role === null || d.default_role === undefined
          ? null
          : String(d.default_role),
      })
    ),
    configs: ((firmPricing.firm_dimension_configs ?? []) as Record<string, unknown>[]).map(
      (c) => ({
        id: String(c.id),
        firmId: String(c.firm_id),
        dimensionId: String(c.dimension_id),
        serviceCatalogEntryId:
          c.service_catalog_entry_id === null || c.service_catalog_entry_id === undefined
            ? null
            : String(c.service_catalog_entry_id),
        parentTierId:
          c.parent_tier_id === null || c.parent_tier_id === undefined
            ? null
            : String(c.parent_tier_id),
        parentOptionId:
          c.parent_option_id === null || c.parent_option_id === undefined
            ? null
            : String(c.parent_option_id),
        role: String(c.role),
        unitId: c.unit_id === null || c.unit_id === undefined ? null : String(c.unit_id),
        guardThreshold: money(c.guard_threshold),
      })
    ),
    tiers: ((firmPricing.firm_tiers ?? []) as Record<string, unknown>[]).map((t) => ({
      id: String(t.id),
      configId: String(t.config_id),
      rangeMin: Number(t.range_min),
      rangeMax: t.range_max === null || t.range_max === undefined ? null : Number(t.range_max),
      price: money(t.price),
      sortOrder: Number(t.sort_order),
    })),
    optionPrices: ((firmPricing.firm_option_prices ?? []) as Record<string, unknown>[]).map(
      (p) => ({
        id: String(p.id),
        optionId: String(p.option_id),
        serviceCatalogEntryId:
          p.service_catalog_entry_id === null || p.service_catalog_entry_id === undefined
            ? null
            : String(p.service_catalog_entry_id),
        price: money(p.price),
      })
    ),
  }
}

// Guard refusal messages surface VERBATIM. The settings screen renders the
// server's own words, because those messages name exactly what will be
// destroyed or why an action is impossible, and a generic replacement would
// throw that away. The fallback fires only when there is genuinely no detail.
export function refusalMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data
    ?.detail
  if (typeof detail === 'string' && detail.length > 0) return detail
  return fallback
}

export const pricingApi = {
  getConfig: async (): Promise<PricingConfig> => {
    const res = await api.get('/api/pricing/config')
    return mapPricingConfig(res.data as Record<string, unknown>)
  },

  upsertCatalogEntry: async (payload: {
    engagementType: string
    isOffered: boolean
    pricingMode: PricingMode | null
    baseFee: number | null
  }) => {
    const res = await api.put(`/api/pricing/catalog/${payload.engagementType}`, {
      engagement_type: payload.engagementType,
      is_offered: payload.isOffered,
      pricing_mode: payload.pricingMode,
      // Sent as-is. null here means "no base fee set", and it must not become 0.
      base_fee: payload.baseFee,
    })
    return res.data
  },

  createConfig: async (payload: {
    dimensionId: string
    role: string
    unitId: string | null
    guardThreshold: number | null
    serviceCatalogEntryId: string | null
    parentTierId: string | null
    parentOptionId: string | null
  }) => {
    const res = await api.post('/api/pricing/configs', {
      dimension_id: payload.dimensionId,
      role: payload.role,
      unit_id: payload.unitId,
      guard_threshold: payload.guardThreshold,
      service_catalog_entry_id: payload.serviceCatalogEntryId,
      parent_tier_id: payload.parentTierId,
      parent_option_id: payload.parentOptionId,
    })
    return res.data
  },

  saveTiers: async (
    configId: string,
    tiers: { rangeMin: number; rangeMax: number | null; price: number | null; sortOrder: number }[]
  ) => {
    const res = await api.put(
      `/api/pricing/configs/${configId}/tiers`,
      tiers.map((t) => ({
        range_min: t.rangeMin,
        range_max: t.rangeMax,
        price: t.price,
        sort_order: t.sortOrder,
      }))
    )
    return res.data
  },

  setOptionPrice: async (payload: {
    optionId: string
    serviceCatalogEntryId: string | null
    price: number | null
  }) => {
    const res = await api.put('/api/pricing/option-prices', {
      option_id: payload.optionId,
      service_catalog_entry_id: payload.serviceCatalogEntryId,
      price: payload.price,
    })
    return res.data
  },

  moveConfig: async (
    configId: string,
    payload: { newParentTierId: string | null; newParentOptionId: string | null; confirm: boolean }
  ) => {
    const res = await api.post(`/api/pricing/configs/${configId}/move`, {
      new_parent_tier_id: payload.newParentTierId,
      new_parent_option_id: payload.newParentOptionId,
      confirm: payload.confirm,
    })
    return res.data
  },

  // Called twice by design. The first call omits confirm so the server refuses
  // with a 422 whose detail is a census of exactly what would be destroyed;
  // that text becomes the confirmation dialog body, so the warning is the
  // server's own count rather than a frontend guess. The second call, after
  // the owner agrees, passes confirm=true.
  deleteConfig: async (configId: string, confirm: boolean) => {
    const res = await api.delete(`/api/pricing/configs/${configId}`, {
      params: { confirm },
    })
    return res.data
  },
}
