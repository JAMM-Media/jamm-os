// path: frontend/src/components/settings/SecurityTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { settingsApi, type StaffAuthPolicy } from '@/lib/api/settingsApi'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

interface PolicyOption {
  value: StaffAuthPolicy
  label: string
  description: string
}

const POLICY_OPTIONS: PolicyOption[] = [
  {
    value: 'either',
    label: 'Password or magic link',
    description:
      'Staff can sign in with either a password or a one-time email link. Recommended for most firms.',
  },
  {
    value: 'password_only',
    label: 'Password only',
    description:
      'Staff must use their password to sign in. Magic links are disabled. Best for firms with strict security requirements.',
  },
  {
    value: 'magic_link_only',
    label: 'Magic link only',
    description:
      'Staff sign in via one-time email links. No passwords required. Eliminates weak password risk.',
  },
]

export default function SecurityTab() {
  const [policy, setPolicy] = useState<StaffAuthPolicy>('either')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    settingsApi
      .getMyFirm()
      .then((r) => {
        const data = r.data as { staff_auth_policy?: string }
        if (data.staff_auth_policy) {
          setPolicy(data.staff_auth_policy as StaffAuthPolicy)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  async function handleSave(selected: StaffAuthPolicy) {
    setPolicy(selected)
    setSaving(true)
    try {
      await settingsApi.updateStaffAuthPolicy(selected)
      toast.success('Login policy updated.')
    } catch {
      toast.error('Could not save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-[#6B7280]" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 max-w-lg">
      <div>
        <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
          Staff login policy
        </p>
        <p className="text-[12px] text-[#6B7280] mb-4">
          Control how your staff members sign in to JAMM PX.
        </p>

        <div className="flex flex-col gap-2">
          {POLICY_OPTIONS.map((opt) => {
            const selected = policy === opt.value
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSave(opt.value)}
                disabled={saving}
                className={cn(
                  'flex items-start gap-3 rounded-[8px] px-3.5 py-3 text-left transition-colors disabled:opacity-70 cursor-pointer',
                  selected
                    ? 'border-[1.5px] border-[#1F3148]'
                    : 'border border-[0.5px] border-[#C8CDD6] hover:border-[#A0A8B4]',
                )}
                style={{ backgroundColor: '#EDEEF0' }}
              >
                {/* Radio dot */}
                <div
                  className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center"
                  style={{
                    border: selected ? '1.5px solid #1F3148' : '1.5px solid #C8CDD6',
                    backgroundColor: selected ? '#1F3148' : 'transparent',
                  }}
                >
                  {selected && (
                    <div className="w-1.5 h-1.5 rounded-full bg-white" />
                  )}
                </div>

                {/* Label + description */}
                <div className="flex flex-col gap-0.5">
                  <span className="text-[13px] font-[500] text-[#1F3148]">{opt.label}</span>
                  <span className="text-[11px] text-[#6B7280] leading-snug">{opt.description}</span>
                </div>
              </button>
            )
          })}
        </div>

        {/* Amber note */}
        <div
          className="mt-3 rounded-[6px] px-3 py-2 text-[11px]"
          style={{ backgroundColor: '#FEF3C7', color: '#92400E' }}
        >
          Your own login always requires a password regardless of this setting.
        </div>

        {/* Save indicator */}
        {saving && (
          <div className="flex items-center gap-2 mt-3 text-[11px] text-[#6B7280]">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Saving...
          </div>
        )}
      </div>
    </div>
  )
}
