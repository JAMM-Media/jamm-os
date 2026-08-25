// frontend/src/components/settings/PricingTab.tsx
//
// The pricing settings tab. Replaces FeeScheduleTab, whose settings blob save
// path is dead and whose 16-item hand-copied engagement list is exactly what
// this exists to remove.
//
// STRUCTURE AND CORRECTNESS ARE THE DELIVERABLE HERE. Ben takes a visual pass
// later. The behaviours that must survive that pass are the ones below, and
// they are behaviours rather than styling:
//
//   - null versus zero rendered as visibly different states everywhere.
//     "Unpriced, routes to quote" is not "$0.00" and the two never collapse.
//   - Guard refusal messages surface VERBATIM from response detail. The server
//     names what it will destroy and why; a generic "something went wrong"
//     throws away the only useful part.
//   - Activation requires a pricing mode in the same action. A service cannot
//     be half-on, and the button stays disabled until a mode is chosen.
//   - An activated but unconfigured service is a LEGITIMATE state, not an
//     error. It says so, plainly, and says what happens to leads.
//
// The complexity configuration section renders inside an open service, below
// that service's activation controls, which is what "the selected engagement
// type" means on this screen: the open row is the selection. It lives in
// ./pricing/ComplexitySection.tsx.

'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  pricingApi,
  refusalMessage,
  type PricingConfig,
  type PricingMode,
  type ServiceCatalogEntry,
} from '@/lib/api/pricing'
import ComplexitySection from './pricing/ComplexitySection'

const PRICING_MODES: { value: PricingMode; label: string; help: string }[] = [
  { value: 'fixed', label: 'Fixed fee', help: 'One price for the service.' },
  { value: 'hourly', label: 'Hourly', help: 'Billed by time at your rate.' },
  { value: 'range', label: 'Range', help: 'A quoted band rather than one number.' },
  {
    value: 'quote_only',
    label: 'Quote only',
    help: 'Always routed to a quote, never priced automatically.',
  },
]

const labelClass =
  'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const inputClass =
  'rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'

// Money in, money out. An empty box means "no base fee", which is null, not 0.
function parseMoney(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const n = Number(trimmed)
  return Number.isNaN(n) ? null : n
}

function formatMoney(value: number | null): string {
  if (value === null) return ''
  return String(value)
}

export default function PricingTab() {
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['pricing-config'],
    queryFn: pricingApi.getConfig,
  })

  // Every successful write invalidates the one config query. The whole screen
  // reads from that single merged payload, so there is nothing else to keep in
  // step and no partial cache to go stale against it.
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['pricing-config'] })
  }

  const upsert = useMutation({
    mutationFn: pricingApi.upsertCatalogEntry,
    onSuccess: () => {
      invalidate()
      toast.success('Saved')
    },
    onError: (err) => {
      // Verbatim. See the note at the top of the file.
      toast.error(refusalMessage(err, 'Could not save this service.'))
    },
  })

  if (isLoading) {
    return (
      <div className="p-6 text-[13px] text-[#6B7280]">Loading pricing configuration...</div>
    )
  }

  if (isError || !data) {
    return (
      <div className="p-6 text-[13px] text-red-600">
        {refusalMessage(error, 'Could not load pricing configuration.')}
      </div>
    )
  }

  const entryFor = (engagementType: string): ServiceCatalogEntry | undefined =>
    data.serviceCatalogEntries.find((e) => e.engagementType === engagementType)

  // A config counts as belonging to a service when it is scoped to that
  // service's catalog entry. Blanket configs (scope null) apply everywhere and
  // are counted separately, below.
  const blanketConfigCount = data.configs.filter(
    (c) => c.serviceCatalogEntryId === null
  ).length

  const configCountFor = (entry: ServiceCatalogEntry | undefined): number => {
    if (!entry) return 0
    return data.configs.filter((c) => c.serviceCatalogEntryId === entry.id).length
  }

  // Grouped by the category the server serves. Uncategorized types render in a
  // trailing ungrouped block rather than being guessed into a bucket, which is
  // the same rule the lead-facing intake form follows.
  const categories: string[] = []
  for (const t of data.engagementTypes) {
    if (t.category && !categories.includes(t.category)) categories.push(t.category)
  }
  const uncategorized = data.engagementTypes.filter((t) => !t.category)

  return (
    <div className="p-6 flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-[15px] font-semibold text-brand dark:text-[#EDEEF0]">
          Services and pricing
        </h2>
        <p className="text-[13px] text-[#6B7280]">
          Every service starts off. Turn on the ones you offer and choose how each one
          is priced. Leads only ever see services you have turned on.
        </p>
      </div>

      {categories.map((category) => (
        <ServiceGroup
          key={category}
          heading={category}
          types={data.engagementTypes.filter((t) => t.category === category)}
          pricing={data}
          entryFor={entryFor}
          configCountFor={configCountFor}
          blanketConfigCount={blanketConfigCount}
          onSave={upsert.mutate}
          saving={upsert.isPending}
        />
      ))}

      {uncategorized.length > 0 && (
        <ServiceGroup
          heading="Other services"
          types={uncategorized}
          pricing={data}
          entryFor={entryFor}
          configCountFor={configCountFor}
          blanketConfigCount={blanketConfigCount}
          onSave={upsert.mutate}
          saving={upsert.isPending}
        />
      )}
    </div>
  )
}

function ServiceGroup({
  heading,
  types,
  pricing,
  entryFor,
  configCountFor,
  blanketConfigCount,
  onSave,
  saving,
}: {
  heading: string
  types: { value: string; label: string; leadFacingLabel: string; category: string | null }[]
  pricing: PricingConfig
  entryFor: (t: string) => ServiceCatalogEntry | undefined
  configCountFor: (e: ServiceCatalogEntry | undefined) => number
  blanketConfigCount: number
  onSave: (p: {
    engagementType: string
    isOffered: boolean
    pricingMode: PricingMode | null
    baseFee: number | null
  }) => void
  saving: boolean
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className={labelClass}>{heading}</div>
      <div className="rounded-[8px] border border-surface-border dark:border-dark-border divide-y divide-surface-border dark:divide-dark-border">
        {types.map((t) => (
          <ServiceRow
            key={t.value}
            type={t}
            pricing={pricing}
            entry={entryFor(t.value)}
            configCount={configCountFor(entryFor(t.value))}
            blanketConfigCount={blanketConfigCount}
            onSave={onSave}
            saving={saving}
          />
        ))}
      </div>
    </div>
  )
}

function ServiceRow({
  type,
  pricing,
  entry,
  configCount,
  blanketConfigCount,
  onSave,
  saving,
}: {
  type: { value: string; label: string; leadFacingLabel: string; category: string | null }
  pricing: PricingConfig
  entry: ServiceCatalogEntry | undefined
  configCount: number
  blanketConfigCount: number
  onSave: (p: {
    engagementType: string
    isOffered: boolean
    pricingMode: PricingMode | null
    baseFee: number | null
  }) => void
  saving: boolean
}) {
  const isOffered = entry?.isOffered ?? false

  // Local edit state for the activation form. Seeded from the saved row so an
  // already-active service opens showing what it actually has.
  const [expanded, setExpanded] = useState(false)
  const [mode, setMode] = useState<PricingMode | ''>(entry?.pricingMode ?? '')
  const [baseFee, setBaseFee] = useState<string>(formatMoney(entry?.baseFee ?? null))

  // THE ACTIVATION LAW, enforced in the UI as well as the service: turning a
  // service on requires choosing a pricing mode in the same action. The server
  // refuses a half-on service with a 422; this keeps the owner from having to
  // meet that refusal to learn the rule.
  const canActivate = mode !== ''

  const totalConfigs = configCount + blanketConfigCount

  return (
    <div className="p-3 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              {type.label}
            </span>
            {isOffered ? (
              <span className="text-[11px] rounded-full px-2 py-0.5 bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300">
                Active
              </span>
            ) : (
              <span className="text-[11px] rounded-full px-2 py-0.5 bg-surface-page dark:bg-dark-page text-[#6B7280] border border-surface-border dark:border-dark-border">
                Off
              </span>
            )}
          </div>
          {/* Read-only, so the owner can see exactly what a lead sees this
              called. Served by the API rather than mapped here on purpose. */}
          <span className="text-[12px] text-[#6B7280] truncate">
            Leads see: {type.leadFacingLabel}
          </span>
        </div>

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-[12px] text-brand dark:text-[#EDEEF0] underline shrink-0"
        >
          {expanded ? 'Close' : isOffered ? 'Edit' : 'Turn on'}
        </button>
      </div>

      {/* An activated service with nothing configured is a real, legitimate
          state and says what it means for leads. It is not an error and is not
          styled as one. */}
      {isOffered && totalConfigs === 0 && (
        <div className="text-[12px] text-[#6B7280] bg-surface-page dark:bg-dark-page rounded-[6px] px-2.5 py-2">
          No pricing configured. New leads route to quote.
        </div>
      )}

      {expanded && (
        <div className="flex flex-col gap-3 pt-1">
          <div className="flex flex-col gap-1.5">
            <span className={labelClass}>How is this priced?</span>
            <div className="flex flex-col gap-1.5">
              {PRICING_MODES.map((m) => (
                <label key={m.value} className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name={`mode-${type.value}`}
                    checked={mode === m.value}
                    onChange={() => setMode(m.value)}
                    className="mt-1"
                  />
                  <span className="flex flex-col">
                    <span className="text-[13px] text-brand dark:text-[#EDEEF0]">
                      {m.label}
                    </span>
                    <span className="text-[12px] text-[#6B7280]">{m.help}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={labelClass}>Base fee</span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={baseFee}
              onChange={(e) => setBaseFee(e.target.value)}
              placeholder="Leave blank for no base fee"
              className={inputClass}
            />
            {/* The null versus zero distinction, said out loud rather than
                implied by an empty box. */}
            <span className="text-[12px] text-[#6B7280]">
              {parseMoney(baseFee) === null
                ? 'Blank means no base fee is set. This service routes to quote unless complexity pricing covers it.'
                : parseMoney(baseFee) === 0
                  ? 'Priced at 0.00. This is a real price, not a blank.'
                  : 'A flat amount applied before any complexity pricing.'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={!canActivate || saving}
              onClick={() =>
                onSave({
                  engagementType: type.value,
                  isOffered: true,
                  pricingMode: mode === '' ? null : mode,
                  baseFee: parseMoney(baseFee),
                })
              }
              className="rounded-[6px] bg-brand text-white text-[13px] px-3 py-1.5 disabled:opacity-50"
            >
              {isOffered ? 'Save changes' : 'Turn on this service'}
            </button>

            {isOffered && (
              <button
                type="button"
                disabled={saving}
                onClick={() =>
                  onSave({
                    engagementType: type.value,
                    isOffered: false,
                    // The mode is kept rather than cleared, so turning the
                    // service back on later restores what it had.
                    pricingMode: mode === '' ? null : mode,
                    baseFee: parseMoney(baseFee),
                  })
                }
                className="rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] px-3 py-1.5 text-brand dark:text-[#EDEEF0] disabled:opacity-50"
              >
                Turn off
              </button>
            )}
          </div>

          {!canActivate && (
            <span className="text-[12px] text-[#6B7280]">
              Choose how this service is priced before turning it on. A service cannot
              be half on.
            </span>
          )}

          {/* Below the activation controls, for the open service. A service
              that is off is not configured here: complexity pricing only ever
              runs for a service a lead can pick. */}
          {/* entry is checked rather than isOffered alone: the section needs
              the catalog entry itself, and a service is only ever offered
              because that row exists. */}
          {entry && isOffered ? (
            <ComplexitySection data={pricing} engagementType={type.value} entry={entry} />
          ) : (
            <div className="text-[12px] text-[#6B7280] pt-3 border-t border-surface-border dark:border-dark-border">
              Turn this service on to configure its complexity pricing.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
