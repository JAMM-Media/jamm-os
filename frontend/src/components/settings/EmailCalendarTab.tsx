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

interface StaffIntegration {
  id: string
  user_id: string
  provider: string
  status: string
  firm_disabled: boolean
}

interface StaffUser {
  id: string
  first_name: string
  last_name: string
  email: string
}

function StatusPill({ status, firmDisabled }: { status: string; firmDisabled: boolean }) {
  if (firmDisabled) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
        Disabled by firm
      </span>
    )
  }
  if (status === 'opted_out') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
        Paused by staff
      </span>
    )
  }
  if (status === 'connected') {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
        Active
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
      Not connected
    </span>
  )
}

function StaffIntegrationControls() {
  const [staffIntegrations, setStaffIntegrations] = useState<StaffIntegration[]>([])
  const [staffUsers, setStaffUsers] = useState<StaffUser[]>([])
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState<Record<string, boolean>>({})

  useEffect(() => {
    async function load() {
      try {
        const [intRes, usersRes] = await Promise.all([
          api.get('/api/v1/integrations/firm/staff'),
          api.get('/api/v1/users/'),
        ])
        setStaffIntegrations(intRes.data)
        setStaffUsers(usersRes.data)
      } catch {
        toast.error('Failed to load staff integrations.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  async function handleToggle(userId: string, provider: string, currentlyDisabled: boolean) {
    const key = `${userId}:${provider}`
    setToggling((prev) => ({ ...prev, [key]: true }))
    const action = currentlyDisabled ? 'enable' : 'disable'

    setStaffIntegrations((prev) =>
      prev.map((i) =>
        i.user_id === userId && i.provider === provider
          ? { ...i, firm_disabled: !currentlyDisabled }
          : i,
      ),
    )

    try {
      await api.post(`/api/v1/integrations/firm/${userId}/${provider}/${action}`)
    } catch {
      setStaffIntegrations((prev) =>
        prev.map((i) =>
          i.user_id === userId && i.provider === provider
            ? { ...i, firm_disabled: currentlyDisabled }
            : i,
        ),
      )
      toast.error('Failed to update integration. Please try again.')
    } finally {
      setToggling((prev) => ({ ...prev, [key]: false }))
    }
  }

  const userIds = Array.from(new Set(staffIntegrations.map((i) => i.user_id)))

  if (loading) {
    return (
      <div className="flex flex-col">
        {[1, 2, 3].map((n) => (
          <div
            key={n}
            className="flex items-start justify-between gap-4 py-2 border-b border-surface-border dark:border-dark-border last:border-0"
            style={{ borderBottomWidth: '0.5px' }}
          >
            <div className="flex-1 flex flex-col gap-1.5">
              <div className="h-3 w-28 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
              <div className="h-3 w-40 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
            </div>
            <div className="flex flex-col gap-2 items-end flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="h-3 w-8 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                <div className="h-4 w-16 bg-surface-border dark:bg-dark-border animate-pulse rounded-full" />
                <div className="h-5 w-14 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
              </div>
              <div className="flex items-center gap-2">
                <div className="h-3 w-10 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                <div className="h-4 w-16 bg-surface-border dark:bg-dark-border animate-pulse rounded-full" />
                <div className="h-5 w-14 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (userIds.length === 0) {
    return (
      <p className="text-[12px] text-[#6B7280]">
        No staff have connected their email yet. Controls will appear here once staff connect their Gmail or Outlook from My Integrations.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {userIds.map((uid) => {
        const user = staffUsers.find((u) => u.id === uid)
        const gmailInt = staffIntegrations.find((i) => i.user_id === uid && i.provider === 'gmail')
        const outlookInt = staffIntegrations.find((i) => i.user_id === uid && i.provider === 'outlook')
        const displayName = user ? `${user.first_name} ${user.last_name}` : 'Unknown'
        const displayEmail = user?.email ?? ''

        return (
          <div
            key={uid}
            className="flex items-start justify-between gap-4 py-2 border-b border-surface-border dark:border-dark-border last:border-0"
            style={{ borderBottomWidth: '0.5px' }}
          >
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-brand dark:text-[#EDEEF0] font-medium truncate">{displayName}</p>
              <p className="text-[11px] text-[#6B7280] truncate">{displayEmail}</p>
            </div>

            <div className="flex flex-col gap-2 items-end flex-shrink-0">
              {(['gmail', 'outlook'] as const).map((provider) => {
                const intRec = provider === 'gmail' ? gmailInt : outlookInt
                if (!intRec) return null
                const key = `${uid}:${provider}`
                const isToggling = toggling[key] ?? false
                return (
                  <div key={provider} className="flex items-center gap-2">
                    <span className="text-[11px] text-[#6B7280] capitalize">{provider}</span>
                    <StatusPill status={intRec.status} firmDisabled={intRec.firm_disabled} />
                    <button
                      disabled={isToggling}
                      onClick={() => handleToggle(uid, provider, intRec.firm_disabled)}
                      className={cn(
                        'text-[11px] px-2 py-0.5 rounded border transition-colors disabled:opacity-50',
                        intRec.firm_disabled
                          ? 'border-brand text-brand dark:border-brand-btn dark:text-brand-btn hover:bg-brand/5'
                          : 'border-red-400 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10',
                      )}
                    >
                      {isToggling ? '...' : intRec.firm_disabled ? 'Enable' : 'Disable'}
                    </button>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
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

      <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-4 border border-surface-border dark:border-dark-border" style={{ borderWidth: '0.5px' }}>
        <div>
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Staff Integration Controls</p>
          <p className="text-[11px] text-[#6B7280] mt-0.5">
            Manage email and calendar sync access for individual staff members. This overrides their personal connection -- disabling here prevents them from using their inbox in JAMM PX regardless of whether they have connected.
          </p>
        </div>
        <StaffIntegrationControls />
      </div>
    </div>
  )
}
