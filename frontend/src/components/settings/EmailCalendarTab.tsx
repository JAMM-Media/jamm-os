// frontend/src/components/settings/EmailCalendarTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import api from '@/lib/api'
import { settingsApi, type FirmDetails } from '@/lib/api/settingsApi'
import { useFetch } from '@/lib/hooks/useFetch'
import { cn } from '@/lib/utils'

interface ToggleProps {
  checked: boolean
  onChange: (val: boolean) => void
  disabled?: boolean
}

function Toggle({ checked, onChange, disabled }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative w-9 h-5 rounded-full transition-colors flex-shrink-0 overflow-hidden disabled:opacity-60',
        checked ? 'bg-brand dark:bg-brand-btn' : 'bg-[#D1D5DB]',
      )}
    >
      <span
        className={cn(
          'absolute top-[3px] left-[3px] w-3.5 h-3.5 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-[16px]' : 'translate-x-0',
        )}
      />
    </button>
  )
}

interface ToggleRowProps {
  label: string
  description: string
  checked: boolean
  onChange: (val: boolean) => void
  saving?: boolean
}

function ToggleRow({ label, description, checked, onChange, saving }: ToggleRowProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1">
        <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{label}</p>
        <p className="text-[11px] text-[#6B7280] mt-0.5">{description}</p>
      </div>
      <Toggle checked={checked} onChange={onChange} disabled={saving} />
    </div>
  )
}

export default function EmailCalendarTab() {
  const { data: firmData } = useFetch<FirmDetails>(
    () => settingsApi.getMyFirm().then((r) => r.data as FirmDetails),
    [],
  )

  const [emailSyncEnabled, setEmailSyncEnabled] = useState(true)
  const [calendarSyncEnabled, setCalendarSyncEnabled] = useState(true)
  const [staffCanDisableEmail, setStaffCanDisableEmail] = useState(true)
  const [staffCanDisableCalendar, setStaffCanDisableCalendar] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!firmData?.settings) return
    const s = firmData.settings as Record<string, unknown>
    setEmailSyncEnabled(s.email_sync_enabled !== false)
    setCalendarSyncEnabled(s.calendar_sync_enabled !== false)
    setStaffCanDisableEmail(s.staff_can_disable_email_sync !== false)
    setStaffCanDisableCalendar(s.staff_can_disable_calendar_sync !== false)
  }, [firmData])

  async function patch(updates: Record<string, boolean>) {
    setSaving(true)
    try {
      await api.patch('/settings/email-calendar-sync', updates)
      toast.success('Settings saved.')
    } catch {
      toast.error('Failed to save. Please try again.')
      if (firmData?.settings) {
        const s = firmData.settings as Record<string, unknown>
        setEmailSyncEnabled(s.email_sync_enabled !== false)
        setCalendarSyncEnabled(s.calendar_sync_enabled !== false)
        setStaffCanDisableEmail(s.staff_can_disable_email_sync !== false)
        setStaffCanDisableCalendar(s.staff_can_disable_calendar_sync !== false)
      }
    } finally {
      setSaving(false)
    }
  }

  function handleToggle(key: string, val: boolean, setter: (v: boolean) => void) {
    setter(val)
    patch({ [key]: val })
  }

  return (
    <div className="flex flex-col gap-4 max-w-lg">
      <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-4 border border-surface-border dark:border-dark-border" style={{ borderWidth: '0.5px' }}>
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Email Sync</p>
        <ToggleRow
          label="Enable email sync"
          description="When on, staff can connect their Gmail or Outlook and see emails inside JAMM PX. When off, the My Integrations page shows a disabled message."
          checked={emailSyncEnabled}
          onChange={(val) => handleToggle('email_sync_enabled', val, setEmailSyncEnabled)}
          saving={saving}
        />
        <ToggleRow
          label="Allow staff to disable email sync"
          description="When on, individual staff members can opt out of email sync even when it is enabled firm-wide."
          checked={staffCanDisableEmail}
          onChange={(val) => handleToggle('staff_can_disable_email_sync', val, setStaffCanDisableEmail)}
          saving={saving}
        />
      </div>

      <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-4 border border-surface-border dark:border-dark-border" style={{ borderWidth: '0.5px' }}>
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Calendar Sync</p>
        <ToggleRow
          label="Enable calendar sync"
          description="When on, staff can sync their calendar events into JAMM PX so appointments appear alongside engagements and tasks."
          checked={calendarSyncEnabled}
          onChange={(val) => handleToggle('calendar_sync_enabled', val, setCalendarSyncEnabled)}
          saving={saving}
        />
        <ToggleRow
          label="Allow staff to disable calendar sync"
          description="When on, individual staff members can opt out of calendar sync even when it is enabled firm-wide."
          checked={staffCanDisableCalendar}
          onChange={(val) => handleToggle('staff_can_disable_calendar_sync', val, setStaffCanDisableCalendar)}
          saving={saving}
        />
      </div>
    </div>
  )
}
