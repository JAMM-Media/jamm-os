// frontend/src/components/settings/pricing/AddDimensionForm.tsx
'use client'
//
// Creating one complexity question on one firm. Every field here maps to one
// field of POST /api/pricing/configs and nothing is invented on the way.
//
// WHAT THIS FORM MIRRORS FROM THE SERVER, AND WHY THAT IS THE WHOLE LIST.
// Two save-time rules are mirrored as disabled-until-answered, following the
// precedent the activation section set: a numeric question needs a unit, and a
// guard needs a threshold. Both are things the owner would otherwise learn by
// being refused, and neither can drift into a wrong answer, since the server
// still enforces them. Nothing else is mirrored. In particular this form does
// not decide whether a parent may take a child, whether a scope combination is
// legal, or whether a dimension may link downhill. Those refusals belong to
// the service and arrive as its own words.
//
// SCOPE DEFAULTS TO BLANKET. Choosing this service instead prefills from the
// blanket configuration as a ONE TIME COPY taken at creation. It is not a
// fallback and it does not stay linked: once created, the override is
// independent and editing the blanket one leaves it alone.

import { useState } from 'react'
import {
  type ComplexityDimension,
  type DimensionRole,
  type PricingConfig,
  type ServiceCatalogEntry,
} from '@/lib/api/pricing'

export interface CreateConfigInput {
  dimensionId: string
  role: DimensionRole
  unitId: string | null
  guardThreshold: number | null
  serviceCatalogEntryId: string | null
  parentTierId: string | null
  parentOptionId: string | null
}

// One place a new question can be hung. Built by the section from what it is
// already rendering, so the picker can only ever name a real tier or option.
export interface ParentChoice {
  kind: 'tier' | 'option'
  id: string
  label: string
  scopeLabel: string
  // Read from the config read, not from a rule. It decides whether the section
  // offers the clear-and-retry path when the server refuses, and nothing else.
  isPriced: boolean
}

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const inputClass =
  'rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'

const ROLES: { value: DimensionRole; label: string; help: string }[] = [
  { value: 'priced', label: 'Priced', help: 'The answer moves the fee.' },
  {
    value: 'informational',
    label: 'Informational',
    help: 'Collected and shown to you, never priced.',
  },
  {
    value: 'guard',
    label: 'Guard',
    help: 'Past a threshold, the lead routes out of automation.',
  },
]

export default function AddDimensionForm({
  data,
  engagementType,
  entry,
  parentChoices,
  onCancel,
  onSubmit,
  submitting,
}: {
  data: PricingConfig
  engagementType: string
  entry: ServiceCatalogEntry
  parentChoices: ParentChoice[]
  onCancel: () => void
  onSubmit: (input: CreateConfigInput) => void
  submitting: boolean
}) {
  const [dimensionId, setDimensionId] = useState('')
  const [role, setRole] = useState<DimensionRole>('priced')
  const [unitId, setUnitId] = useState('')
  const [guardThreshold, setGuardThreshold] = useState('')
  const [scoped, setScoped] = useState(false)
  const [structure, setStructure] = useState<'additive' | 'matrix'>('additive')
  const [parentKey, setParentKey] = useState('')

  // Only questions the system catalog maps to this service. A blanket config
  // applies to a service through that map, so a question the map does not link
  // here could be configured but would never be asked.
  const available: ComplexityDimension[] = data.dimensions.filter((d) =>
    data.flagEngagementTypes.some(
      (fe) => fe.flagId === d.flagId && fe.engagementType === engagementType
    )
  )

  const dimension = available.find((d) => d.id === dimensionId)
  const units = dimension ? data.dimensionUnits.filter((u) => u.dimensionId === dimension.id) : []
  const flagNameFor = (d: ComplexityDimension): string =>
    data.flags.find((f) => f.id === d.flagId)?.name ?? d.key

  // The blanket configuration of this same question, if the firm has one. It
  // is the source of the one time copy below.
  const blanketSource = dimension
    ? data.configs.find(
        (c) => c.dimensionId === dimension.id && c.serviceCatalogEntryId === null
      )
    : undefined

  const applyDimension = (nextId: string) => {
    setDimensionId(nextId)
    const next = available.find((d) => d.id === nextId)
    // Role prefills from the catalog default, which is what the system expects
    // this question to be used for. The owner can still change it.
    setRole(next?.defaultRole ?? 'priced')
    const nextUnits = next ? data.dimensionUnits.filter((u) => u.dimensionId === next.id) : []
    setUnitId(nextUnits.length === 1 ? nextUnits[0].id : '')
    setGuardThreshold('')
  }

  // The one time copy. Taken when the owner switches this question to an
  // override, from the blanket config as it stands right now. Nothing stays
  // linked afterwards.
  const applyScope = (nextScoped: boolean) => {
    setScoped(nextScoped)
    if (!nextScoped || !blanketSource) return
    setRole(blanketSource.role)
    setUnitId(blanketSource.unitId ?? '')
    setGuardThreshold(
      blanketSource.guardThreshold === null ? '' : String(blanketSource.guardThreshold)
    )
  }

  const needsUnit = dimension?.kind === 'numeric_range'
  const needsThreshold = role === 'guard'
  const parent = parentChoices.find((p) => p.kind + ':' + p.id === parentKey)

  const canSubmit =
    dimension !== undefined &&
    (!needsUnit || unitId !== '') &&
    (!needsThreshold || guardThreshold.trim() !== '') &&
    (structure === 'additive' || parent !== undefined)

  const submit = () => {
    if (!dimension || !canSubmit) return
    onSubmit({
      dimensionId: dimension.id,
      role,
      unitId: needsUnit ? unitId : null,
      // Blank is not zero here either. A guard with no threshold sends null and
      // the server refuses it by name.
      guardThreshold:
        guardThreshold.trim() === '' || Number.isNaN(Number(guardThreshold))
          ? null
          : Number(guardThreshold),
      serviceCatalogEntryId: scoped ? entry.id : null,
      parentTierId: structure === 'matrix' && parent?.kind === 'tier' ? parent.id : null,
      parentOptionId: structure === 'matrix' && parent?.kind === 'option' ? parent.id : null,
    })
  }

  return (
    <div className="rounded-[6px] border border-surface-border dark:border-dark-border p-3 flex flex-col gap-3">
      <span className={labelClass}>Add a complexity question</span>

      <div className="flex flex-col gap-1.5">
        <span className={labelClass}>Question</span>
        <select
          value={dimensionId}
          onChange={(e) => applyDimension(e.target.value)}
          className={inputClass}
        >
          <option value="">Choose a question</option>
          {available.map((d) => (
            <option key={d.id} value={d.id}>
              {flagNameFor(d)}: {d.questionText ?? d.key}
            </option>
          ))}
        </select>
        {available.length === 0 && (
          <span className="text-[12px] text-[#6B7280]">
            The catalog maps no complexity questions to this service.
          </span>
        )}
      </div>

      {dimension && (
        <>
          {needsUnit && (
            <div className="flex flex-col gap-1.5">
              <span className={labelClass}>Counted in</span>
              <select
                value={unitId}
                onChange={(e) => setUnitId(e.target.value)}
                className={inputClass}
              >
                <option value="">Choose a unit</option>
                {units.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.label}
                  </option>
                ))}
              </select>
              <span className="text-[12px] text-[#6B7280]">
                A number question is priced in bands, and the unit names what is being
                counted.
              </span>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <span className={labelClass}>What is this question for?</span>
            {ROLES.map((r) => (
              <label key={r.value} className="flex items-start gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="role"
                  checked={role === r.value}
                  onChange={() => setRole(r.value)}
                  className="mt-1"
                />
                <span className="flex flex-col">
                  <span className="text-[13px] text-brand dark:text-[#EDEEF0]">{r.label}</span>
                  <span className="text-[12px] text-[#6B7280]">{r.help}</span>
                </span>
              </label>
            ))}
          </div>

          {needsThreshold && (
            <div className="flex flex-col gap-1.5">
              <span className={labelClass}>Guard threshold</span>
              <input
                type="number"
                step="0.01"
                value={guardThreshold}
                onChange={(e) => setGuardThreshold(e.target.value)}
                className={inputClass}
              />
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <span className={labelClass}>Where does it apply?</span>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="scope"
                checked={!scoped}
                onChange={() => applyScope(false)}
                className="mt-1"
              />
              <span className="flex flex-col">
                <span className="text-[13px] text-brand dark:text-[#EDEEF0]">Every service</span>
                <span className="text-[12px] text-[#6B7280]">
                  Applies wherever the catalog maps this question.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="scope"
                checked={scoped}
                onChange={() => applyScope(true)}
                className="mt-1"
              />
              <span className="flex flex-col">
                <span className="text-[13px] text-brand dark:text-[#EDEEF0]">
                  This service only
                </span>
                <span className="text-[12px] text-[#6B7280]">
                  An override for this service. Scope cannot be changed later: an override
                  that turns out to be wrong is deleted and made again.
                </span>
              </span>
            </label>
            {scoped && blanketSource && (
              <span className="text-[12px] text-[#6B7280]">
                Prefilled by copying what you already set for every service. This is a copy
                taken now, not a link. Once created, the two are independent.
              </span>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={labelClass}>How does it price?</span>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="structure"
                checked={structure === 'additive'}
                onChange={() => setStructure('additive')}
                className="mt-1"
              />
              <span className="flex flex-col">
                <span className="text-[13px] text-brand dark:text-[#EDEEF0]">On its own</span>
                <span className="text-[12px] text-[#6B7280]">
                  The answer carries its own amounts and adds to the fee.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="radio"
                name="structure"
                checked={structure === 'matrix'}
                onChange={() => setStructure('matrix')}
                className="mt-1"
              />
              <span className="flex flex-col">
                <span className="text-[13px] text-brand dark:text-[#EDEEF0]">
                  Inside another answer
                </span>
                <span className="text-[12px] text-[#6B7280]">
                  Asked only when the lead gave a particular answer above, and priced there
                  instead of on the answer above it.
                </span>
              </span>
            </label>
          </div>

          {structure === 'matrix' && (
            <div className="flex flex-col gap-1.5">
              <span className={labelClass}>Nest under</span>
              <select
                value={parentKey}
                onChange={(e) => setParentKey(e.target.value)}
                className={inputClass}
              >
                <option value="">Choose an answer</option>
                {parentChoices.map((p) => (
                  <option key={p.kind + ':' + p.id} value={p.kind + ':' + p.id}>
                    {p.label} ({p.scopeLabel})
                  </option>
                ))}
              </select>
              {parentChoices.length === 0 && (
                <span className="text-[12px] text-[#6B7280]">
                  There is nothing to nest under yet. Add a question on its own first.
                </span>
              )}
              {parent?.isPriced && (
                <span className="text-[12px] text-[#6B7280]">
                  That answer currently carries a price. Prices live only at the end of a
                  chain, so its price has to be cleared before anything can hang under it.
                  You will be asked to confirm that.
                </span>
              )}
            </div>
          )}
        </>
      )}

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!canSubmit || submitting}
          onClick={submit}
          className="rounded-[6px] bg-brand text-white text-[13px] px-3 py-1.5 disabled:opacity-50"
        >
          Add question
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] px-3 py-1.5 text-brand dark:text-[#EDEEF0]"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
