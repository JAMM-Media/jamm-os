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

interface FeeScheduleTabProps {
  firmSettings: Record<string, unknown> | null
  onSaved: () => void
}

export default function FeeScheduleTab({ firmSettings, onSaved }: FeeScheduleTabProps) {
  const [fees, setFees] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    const existing = (firmSettings?.fee_schedule as Record<string, string>) ?? {}
    setFees(existing)
    setDirty(false)
  }, [firmSettings])

  function handleChange(key: string, value: string) {
    setFees((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.patch('/users/firm/settings', { fee_schedule: fees })
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
