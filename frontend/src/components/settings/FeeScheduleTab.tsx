// frontend/src/components/settings/FeeScheduleTab.tsx
'use client'

import { useState, useEffect } from 'react'
import api from '@/lib/api'
import { toast } from 'sonner'

// All engagement types with human-readable labels grouped by category
const FEE_SCHEDULE_ITEMS = [
  { category: 'Tax Returns', items: [
    { key: 'tax_return_1040', label: '1040 — Individual' },
    { key: 'tax_return_1120', label: '1120 — C-Corporation' },
    { key: 'tax_return_1120s', label: '1120-S — S-Corporation' },
    { key: 'tax_return_1065', label: '1065 — Partnership' },
    { key: 'tax_return_1041', label: '1041 — Trust / Estate Income' },
    { key: 'tax_return_706', label: '706 — Estate Tax' },
    { key: 'amended_return_1040x', label: '1040-X — Amended Return' },
  ]},
  { category: 'Extensions', items: [
    { key: 'extension_4868', label: '4868 — Individual Extension' },
    { key: 'extension_7004', label: '7004 — Business Extension' },
    { key: 'extension_8868', label: '8868 — Exempt Org Extension' },
  ]},
  { category: 'Bookkeeping', items: [
    { key: 'bookkeeping_monthly', label: 'Monthly Bookkeeping' },
    { key: 'bookkeeping_quarterly', label: 'Quarterly Bookkeeping' },
  ]},
  { category: 'Payroll', items: [
    { key: 'payroll_tax_941', label: '941 — Quarterly Payroll Tax' },
  ]},
  { category: 'Other Services', items: [
    { key: 'tax_planning_advisory', label: 'Tax Planning / Advisory' },
    { key: 'audit_representation', label: 'Audit Representation' },
    { key: 'custom', label: 'Other / Custom' },
  ]},
]

const FIXED_ADDER_FLAGS = [
  { key: 'rental_property', label: 'Rental Property' },
  { key: 'foreign_accounts_fbar', label: 'Foreign Accounts / FBAR' },
  { key: 'depreciation_schedules', label: 'Depreciation Schedules' },
  { key: 'home_office', label: 'Home Office Deduction' },
  { key: 'multiple_states', label: 'Multiple States' },
  { key: 'trust_estate_involvement', label: 'Trust or Estate Involvement' },
  { key: 'business_sale', label: 'Business Sale or Disposition' },
  { key: 'equity_compensation', label: 'Equity Compensation / ISO / RSU' },
]

const TIERED_ADDER_FLAGS = [
  { key: 'k1_involvement', label: 'K-1 Involvement' },
  { key: 'crypto', label: 'Cryptocurrency Transactions' },
]

type Tier = { label: string; amount: string }
type ComplexityAdders = Record<string, string | Tier[]>

interface FeeScheduleTabProps {
  firmSettings: Record<string, unknown> | null
  onSaved: () => void
}

export default function FeeScheduleTab({ firmSettings, onSaved }: FeeScheduleTabProps) {
  const [fees, setFees] = useState<Record<string, string>>({})
  const [complexityAdders, setComplexityAdders] = useState<ComplexityAdders>({})
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    const existing = (firmSettings?.fee_schedule as Record<string, unknown>) ?? {}
    const { complexity_adders, ...baseRates } = existing as { complexity_adders?: ComplexityAdders } & Record<string, string>
    setFees(baseRates as Record<string, string>)
    setComplexityAdders(complexity_adders ?? {})
    setDirty(false)
  }, [firmSettings])

  function handleChange(key: string, value: string) {
    setFees((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  function handleFixedAdderChange(key: string, value: string) {
    setComplexityAdders((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  function handleTierChange(flagKey: string, index: number, field: 'label' | 'amount', value: string) {
    setComplexityAdders((prev) => {
      const existing = (prev[flagKey] as Tier[] | undefined) ?? []
      const updated = existing.map((t, i) => i === index ? { ...t, [field]: value } : t)
      return { ...prev, [flagKey]: updated }
    })
    setDirty(true)
  }

  function handleAddTier(flagKey: string) {
    setComplexityAdders((prev) => {
      const existing = (prev[flagKey] as Tier[] | undefined) ?? []
      return { ...prev, [flagKey]: [...existing, { label: '', amount: '' }] }
    })
    setDirty(true)
  }

  function handleRemoveTier(flagKey: string, index: number) {
    setComplexityAdders((prev) => {
      const existing = (prev[flagKey] as Tier[] | undefined) ?? []
      return { ...prev, [flagKey]: existing.filter((_, i) => i !== index) }
    })
    setDirty(true)
  }

  async function handleSave() {
    setSaving(true)
    try {
      const feeSchedule = { ...fees, complexity_adders: complexityAdders }
      await api.patch('/users/firm/settings', { fee_schedule: feeSchedule })
      toast.success('Fee schedule saved')
      setDirty(false)
      onSaved()
    } catch {
      toast.error('Failed to save fee schedule')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div>
        <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">Fee Schedule</h2>
        <p className="text-[12px] text-[#6B7280] mt-0.5">
          Set your standard fees per engagement type. These auto-populate when sending engagement letters.
          Leave blank for types you don&apos;t offer or prefer to price individually.
        </p>
      </div>

      {FEE_SCHEDULE_ITEMS.map((group) => (
        <div key={group.category} className="flex flex-col gap-3">
          <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
            {group.category}
          </p>
          <div className="bg-surface-card dark:bg-dark-card rounded-[8px] overflow-hidden">
            {group.items.map((item, idx) => (
              <div
                key={item.key}
                className={`flex items-center justify-between px-4 py-3 gap-4 ${
                  idx < group.items.length - 1
                    ? 'border-b border-surface-border dark:border-dark-border'
                    : ''
                }`}
              >
                <span className="text-[13px] text-brand dark:text-[#EDEEF0] flex-1">
                  {item.label}
                </span>
                <div className="relative flex items-center">
                  <span className="absolute left-3 text-[13px] text-[#6B7280]">$</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={fees[item.key] ?? ''}
                    onChange={(e) => handleChange(item.key, e.target.value)}
                    placeholder="—"
                    className="w-28 pl-6 pr-3 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] text-right"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Complexity Adders section */}
      <div className="flex flex-col gap-3">
        <div>
          <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
            Complexity Adders
          </p>
          <p className="text-[11px] text-[#6B7280] mt-1">
            Additional fees added to the base rate when complexity flags are selected on an engagement letter.
          </p>
        </div>

        {/* Fixed flags */}
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] overflow-hidden">
          {FIXED_ADDER_FLAGS.map((flag, idx) => (
            <div
              key={flag.key}
              className={`flex items-center justify-between px-4 py-3 gap-4 ${
                idx < FIXED_ADDER_FLAGS.length - 1
                  ? 'border-b border-surface-border dark:border-dark-border'
                  : ''
              }`}
            >
              <span className="text-[13px] text-brand dark:text-[#EDEEF0] flex-1">
                {flag.label}
              </span>
              <div className="relative flex items-center">
                <span className="absolute left-3 text-[13px] text-[#6B7280]">$</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={(complexityAdders[flag.key] as string) ?? ''}
                  onChange={(e) => handleFixedAdderChange(flag.key, e.target.value)}
                  placeholder="—"
                  className="w-28 pl-6 pr-3 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] text-right"
                />
              </div>
            </div>
          ))}
        </div>

        {/* Tiered flags */}
        {TIERED_ADDER_FLAGS.map((flag) => {
          const tiers = (complexityAdders[flag.key] as Tier[] | undefined) ?? []
          return (
            <div key={flag.key} className="flex flex-col gap-2">
              <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{flag.label}</p>
              <div className="bg-surface-card dark:bg-dark-card rounded-[8px] overflow-hidden">
                {tiers.map((tier, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center gap-3 px-4 py-3 ${
                      idx < tiers.length - 1
                        ? 'border-b border-surface-border dark:border-dark-border'
                        : ''
                    }`}
                  >
                    <input
                      type="text"
                      value={tier.label}
                      onChange={(e) => handleTierChange(flag.key, idx, 'label', e.target.value)}
                      placeholder="e.g. 1-3 K-1s"
                      className="flex-1 px-3 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
                    />
                    <div className="relative flex items-center">
                      <span className="absolute left-3 text-[13px] text-[#6B7280]">$</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={tier.amount}
                        onChange={(e) => handleTierChange(flag.key, idx, 'amount', e.target.value)}
                        placeholder="—"
                        className="w-28 pl-6 pr-3 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] text-right"
                      />
                    </div>
                    <button
                      onClick={() => handleRemoveTier(flag.key, idx)}
                      className="flex items-center justify-center w-6 h-6 rounded-full text-[#6B7280] hover:text-red-500 hover:bg-surface-page dark:hover:bg-dark-page transition-colors flex-shrink-0"
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M1 1l10 10M11 1L1 11" />
                      </svg>
                    </button>
                  </div>
                ))}
                <div className={`px-4 py-2.5 ${tiers.length > 0 ? 'border-t border-surface-border dark:border-dark-border' : ''}`}>
                  <button
                    onClick={() => handleAddTier(flag.key)}
                    className="text-[12px] text-[#4A7FA5] hover:text-brand transition-colors"
                  >
                    + Add Tier
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between pt-2">
        <p className="text-[11px] text-[#6B7280]">
          Fee amounts are stored per firm and used to pre-fill engagement letters.
          They are never shared with clients directly.
        </p>
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Saving...' : 'Save Fee Schedule'}
        </button>
      </div>
    </div>
  )
}
