// frontend/src/app/settings/page.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import { Eye, EyeOff, Plug, CheckCircle2, ChevronLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import api from '@/lib/api'
import { settingsApi, type FirmDetails, type StaffMember } from '@/lib/api/settingsApi'
import AutomationsTab from '@/components/settings/AutomationsTab'
import SecurityTab from '@/components/settings/SecurityTab'
import FeeScheduleTab from '@/components/settings/FeeScheduleTab'
import PortalBrandingTab from '@/components/settings/PortalBrandingTab'
import MigrationTab from '@/components/settings/MigrationTab'
import SendingDomainTab from '@/components/settings/SendingDomainTab'
import PortalDomainTab from '@/components/settings/PortalDomainTab'
import EmailCalendarTab from '@/components/settings/EmailCalendarTab'
import { onConciergeAction, setFormDirty } from '@/lib/events/conciergeEvents'

interface Integration {
  id: string
  provider: string
  status: string
  external_account_id: string | null
}

function MyIntegrationsTabContent() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [firmSettings, setFirmSettings] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [pausing, setPausing] = useState<string | null>(null)
  const [resuming, setResuming] = useState<string | null>(null)

  async function fetchData() {
    try {
      const [intResp, firmResp] = await Promise.all([
        api.get('/api/v1/integrations/staff/me'),
        settingsApi.getMyFirm(),
      ])
      setIntegrations(intResp.data ?? [])
      setFirmSettings((firmResp.data as FirmDetails)?.settings ?? {})
    } catch {
      toast.error('Failed to load integrations.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    const connected = params.get('connected')
    const error = params.get('error')
    if (connected === 'gmail') toast.success('Gmail connected successfully.')
    if (connected === 'outlook') toast.success('Outlook connected successfully.')
    if (error === 'gmail_failed') toast.error('Gmail connection failed. Please try again.')
    if (error === 'outlook_failed') toast.error('Outlook connection failed. Please try again.')
  }, [])

  async function handleConnect(provider: 'gmail' | 'outlook') {
    setConnecting(provider)
    try {
      const resp = await api.get(`/api/v1/integrations/staff/${provider}/connect`)
      window.location.href = resp.data.authorization_url
    } catch {
      toast.error(`Failed to start ${provider} connection.`)
      setConnecting(null)
    }
  }

  async function handleDisconnect(provider: string) {
    setDisconnecting(provider)
    try {
      await api.delete(`/api/v1/integrations/staff/${provider}`)
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} disconnected.`)
      await fetchData()
    } catch {
      toast.error('Failed to disconnect. Please try again.')
    } finally {
      setDisconnecting(null)
    }
  }

  async function handlePause(provider: string) {
    setPausing(provider)
    try {
      await api.post(`/api/v1/integrations/staff/${provider}/disable`)
      toast.success('Inbox sync paused.')
      await fetchData()
    } catch {
      toast.error('Failed to pause inbox sync. Please try again.')
    } finally {
      setPausing(null)
    }
  }

  async function handleResume(provider: string) {
    setResuming(provider)
    try {
      await api.post(`/api/v1/integrations/staff/${provider}/enable`)
      toast.success('Inbox sync resumed.')
      await fetchData()
    } catch {
      toast.error('Failed to resume inbox sync. Please try again.')
    } finally {
      setResuming(null)
    }
  }

  function getIntegration(provider: string): Integration | undefined {
    return integrations.find((i) => i.provider === provider)
  }

  const emailSyncEnabled = firmSettings.email_sync_enabled !== false
  const staffCanDisable = firmSettings.staff_can_disable_email_sync !== false

  const providers: { key: 'gmail' | 'outlook'; label: string }[] = [
    { key: 'gmail', label: 'Gmail' },
    { key: 'outlook', label: 'Outlook' },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">My Integrations</h2>
        <p className="text-[12px] text-[#6B7280] mt-0.5">
          Connect your Gmail or Outlook to JAMM PX. Your emails and calendar events are private to you.
        </p>
      </div>

      {loading ? (
        <div className="flex flex-col gap-3 max-w-lg">
          {[1, 2].map((i) => (
            <div key={i} className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 h-[88px] animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3 max-w-lg">
          {providers.map(({ key, label }) => {
            const integration = getIntegration(key)
            const connected = integration?.status === 'connected'
            const optedOut = integration?.status === 'opted_out'

            if (!emailSyncEnabled) {
              return (
                <div
                  key={key}
                  className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex items-center gap-4 border border-surface-border dark:border-dark-border"
                  style={{ borderWidth: '0.5px' }}
                >
                  <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#F3F4F6] dark:bg-[#333333] flex-shrink-0">
                    <Plug className="h-4 w-4 text-[#9CA3AF]" />
                  </div>
                  <div className="flex-1">
                    <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{label}</p>
                    <p className="text-[11px] text-[#9CA3AF] mt-0.5">
                      Email sync is disabled by your firm owner.
                    </p>
                  </div>
                </div>
              )
            }

            return (
              <div
                key={key}
                className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex items-center gap-4 border border-surface-border dark:border-dark-border"
                style={{ borderWidth: '0.5px' }}
              >
                <div
                  className={cn(
                    'flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0',
                    connected
                      ? 'bg-[#D1FAE5] dark:bg-[#064E3B]/30'
                      : optedOut
                      ? 'bg-[#FEF3C7] dark:bg-[#78350F]/30'
                      : 'bg-[#F3F4F6] dark:bg-[#333333]',
                  )}
                >
                  {connected ? (
                    <CheckCircle2 className="h-4 w-4 text-[#059669]" />
                  ) : optedOut ? (
                    <Plug className="h-4 w-4 text-[#D97706]" />
                  ) : (
                    <Plug className="h-4 w-4 text-[#6B7280]" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{label}</p>
                    {connected && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
                        Connected
                      </span>
                    )}
                    {optedOut && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E]">
                        Paused
                      </span>
                    )}
                  </div>
                  {(connected || optedOut) && integration?.external_account_id && (
                    <p className="text-[11px] text-[#6B7280] mt-0.5 truncate">
                      {integration.external_account_id}
                    </p>
                  )}
                  {!connected && !optedOut && (
                    <p className="text-[11px] text-[#9CA3AF] mt-0.5">Not connected</p>
                  )}
                </div>
                <div className="flex-shrink-0 flex flex-col items-end gap-1">
                  {(connected || optedOut) ? (
                    <>
                      <button
                        onClick={() => handleDisconnect(key)}
                        disabled={disconnecting === key}
                        className="h-7 px-3 text-[12px] font-medium rounded-[6px] border border-[#E5E7EB] dark:border-dark-border text-[#6B7280] hover:text-[#DC2626] hover:border-[#DC2626] transition-colors disabled:opacity-60"
                      >
                        {disconnecting === key ? 'Disconnecting...' : 'Disconnect'}
                      </button>
                      {staffCanDisable && (
                        optedOut ? (
                          <button
                            onClick={() => handleResume(key)}
                            disabled={resuming === key}
                            className="text-[11px] text-[#4A7FA5] hover:underline disabled:opacity-60"
                          >
                            {resuming === key ? 'Resuming...' : 'Resume inbox'}
                          </button>
                        ) : (
                          <button
                            onClick={() => handlePause(key)}
                            disabled={pausing === key}
                            className="text-[11px] text-[#6B7280] hover:underline disabled:opacity-60"
                          >
                            {pausing === key ? 'Pausing...' : 'Pause inbox'}
                          </button>
                        )
                      )}
                    </>
                  ) : (
                    <button
                      onClick={() => handleConnect(key)}
                      disabled={connecting === key}
                      className="h-7 px-3 text-[12px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60"
                    >
                      {connecting === key ? 'Redirecting...' : `Connect ${label}`}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const TABS = [
  { key: 'my_integrations', label: 'My Integrations' },
  { key: 'profile', label: 'Profile' },
  { key: 'firm', label: 'Firm' },
  { key: 'team', label: 'Team' },
  { key: 'security', label: 'Security' },
  { key: 'automations', label: 'Automations' },
  { key: 'fee_schedule', label: 'Fee Schedule' },
  { key: 'portal_branding', label: 'Portal' },
  { key: 'sending_domain', label: 'Email Domain' },
  { key: 'portal_domain', label: 'Portal Domain' },
  { key: 'email_calendar', label: 'Email & Calendar' },
  { key: 'migration', label: 'Migration' },
]

const SECTIONS = [
  { label: 'Account', keys: ['my_integrations', 'profile', 'security'] },
  { label: 'Firm Settings', keys: ['firm', 'team', 'automations', 'fee_schedule'] },
  { label: 'Portal', keys: ['portal_branding', 'portal_domain'] },
  { label: 'Email', keys: ['sending_domain', 'email_calendar'] },
  { label: 'Data', keys: ['migration'] },
]

function formatRoleLabel(role: string): string {
  if (role === 'firm_owner') return 'Partner'
  return role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function RoleBadge({ role }: { role: string }) {
  if (role === 'firm_owner') {
    return (
      <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#DBEAFE] text-[#1E40AF]">
        {formatRoleLabel(role)}
      </span>
    )
  }
  if (role === 'manager') {
    return (
      <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E]">
        {formatRoleLabel(role)}
      </span>
    )
  }
  return (
    <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#E5E7EB] text-[#6B7280]">
      {formatRoleLabel(role)}
    </span>
  )
}

function DataExportSection() {
  const [exporting, setExporting] = useState(false)
  const [requestingArchive, setRequestingArchive] = useState(false)

  async function handleExport() {
    setExporting(true)
    try {
      const response = await api.get('/api/v1/firm-export/download', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const disposition = response.headers['content-disposition'] ?? ''
      const match = disposition.match(/filename="([^"]+)"/)
      link.setAttribute('download', match ? match[1] : 'jammpx_export.zip')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      toast.success('Export downloaded')
    } catch {
      toast.error('Export failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  async function handleRequestArchive() {
    setRequestingArchive(true)
    try {
      await api.post('/api/v1/firm-export/request-document-archive')
      toast.success('Document archive requested. You will receive an email with a download link shortly.')
    } catch {
      toast.error('Request failed. Please try again.')
    } finally {
      setRequestingArchive(false)
    }
  }

  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-3 max-w-lg" style={{ marginTop: '12px' }}>
      <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Data export</p>
      <p className="text-[12px] text-[#6B7280]">
        Download a complete export of your firm data as a ZIP file containing CSVs for all clients, engagements, invoices, tasks, IRS authorizations, notes, time entries, and documents.
      </p>
      <div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2"
        >
          {exporting && (
            <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {exporting ? 'Exporting...' : 'Download export'}
        </button>
      </div>
      <div className="flex flex-col gap-1">
        <button
          onClick={handleRequestArchive}
          disabled={requestingArchive}
          className="h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2 w-fit"
        >
          {requestingArchive && (
            <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {requestingArchive ? 'Requesting...' : 'Request document archive'}
        </button>
        <p className="text-[11px] text-[#6B7280]">Large archives may take a few minutes. A download link will be sent to your email.</p>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile')
  const { user } = useAuth()
  const [approvalRequired, setApprovalRequired] = useState<boolean | null>(null)
  const [savingApproval, setSavingApproval] = useState(false)

  const [emailReplyTo, setEmailReplyTo] = useState('')
  const [emailDisplayName, setEmailDisplayName] = useState('')
  const [savingEmail, setSavingEmail] = useState(false)

  const [googleReviewUrl, setGoogleReviewUrl] = useState('')
  const [reviewEnabled, setReviewEnabled] = useState(false)
  const [savingReview, setSavingReview] = useState(false)

  const { data: firmData, isLoading: firmLoading } = useFetch<FirmDetails>(
    () => settingsApi.getMyFirm().then((r) => r.data as FirmDetails),
    []
  )

  const { data: teamData, isLoading: teamLoading, refetch: refetchTeam } = useFetch<StaffMember[]>(
    () => settingsApi.listTeam().then((r) => (r.data as { items: StaffMember[] }).items),
    []
  )
  const team = teamData ?? []

  const [inviteFullName, setInviteFullName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [invitePassword, setInvitePassword] = useState('')
  const [inviteRole, setInviteRole] = useState<'staff' | 'manager' | 'firm_owner'>('staff')
  const [inviteSubmitting, setInviteSubmitting] = useState(false)
  const [showInvitePassword, setShowInvitePassword] = useState(false)
  const [invitePasswordLocked, setInvitePasswordLocked] = useState(false)
  const inviteFormRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const raw = sessionStorage.getItem('jamm_concierge_pending')
    if (!raw) return
    try {
      const action = JSON.parse(raw)
      if (Date.now() - (action._ts ?? 0) > 10000) {
        sessionStorage.removeItem('jamm_concierge_pending')
        return
      }
      if (action.modal === 'invite-staff') {
        sessionStorage.removeItem('jamm_concierge_pending')
        setActiveTab('team')
        setTimeout(() => inviteFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 400)
      }
    } catch {
      sessionStorage.removeItem('jamm_concierge_pending')
    }
  }, [])

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'invite-staff') {
        setActiveTab('team')
        setTimeout(() => {
          inviteFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }, 150)
      }
    })
  }, [])

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    setInviteSubmitting(true)
    try {
      await api.post('/users/', {
        full_name: inviteFullName,
        email: inviteEmail,
        password: invitePassword,
        role: inviteRole,
      })
      setFormDirty(false)
      toast.success('Team member added.')
      setInviteFullName('')
      setInviteEmail('')
      setInvitePassword('')
      setInviteRole('staff')
      refetchTeam()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Something went wrong.')
    } finally {
      setInviteSubmitting(false)
    }
  }

  useEffect(() => {
    if (firmData && approvalRequired === null) {
      setApprovalRequired((firmData as FirmDetails & { timesheet_approval_required?: boolean }).timesheet_approval_required ?? false)
    }
  }, [firmData, approvalRequired])

  useEffect(() => {
    if (firmData?.settings) {
      setEmailReplyTo((firmData.settings.email_reply_to as string) ?? '')
      setEmailDisplayName((firmData.settings.email_display_name as string) ?? '')
      setGoogleReviewUrl((firmData.settings.google_review_url as string) ?? '')
    }
    setReviewEnabled((firmData as (FirmDetails & { feature_flags?: Record<string, unknown> }) | undefined)?.feature_flags?.review_requests_enabled === true)
  }, [firmData])

  async function handleSaveEmailSettings() {
    setSavingEmail(true)
    try {
      await api.patch('/settings/email', {
        reply_to: emailReplyTo || null,
        display_name: emailDisplayName || null,
      })
      toast.success('Email settings saved')
    } catch {
      toast.error('Failed to save email settings')
    } finally {
      setSavingEmail(false)
    }
  }

  async function handleSaveReviewSettings() {
    setSavingReview(true)
    try {
      await api.patch('/settings/review', {
        google_review_url: googleReviewUrl || null,
        review_requests_enabled: reviewEnabled,
      })
      toast.success('Review settings saved')
    } catch {
      toast.error('Failed to save review settings')
    } finally {
      setSavingReview(false)
    }
  }

  async function handleToggleApproval() {
    if (!isFirmOwner) return
    const next = !approvalRequired
    setApprovalRequired(next)
    setSavingApproval(true)
    try {
      await api.patch('/api/v1/firms/me', { timesheet_approval_required: next })
      toast.success('Timesheet setting saved')
    } catch {
      setApprovalRequired(!next)
      toast.error('Failed to save setting')
    } finally {
      setSavingApproval(false)
    }
  }

  const isFirmOwner = user?.role === 'firm_owner'
  const canSeeAutomations = user?.role === 'firm_owner' || user?.role === 'manager'
  const canSeeSecurity = isFirmOwner
  const canSeeSendingDomain = isFirmOwner
  const canSeePortalDomain = isFirmOwner
  const canSeeEmailCalendar = isFirmOwner
  const canSeeMigration = isFirmOwner

  const router = useRouter()

  function isTabVisible(key: string): boolean {
    if (key === 'my_integrations') return true
    if (key === 'automations') return canSeeAutomations
    if (key === 'security') return canSeeSecurity
    if (key === 'fee_schedule') return isFirmOwner
    if (key === 'portal_branding') return isFirmOwner
    if (key === 'sending_domain') return canSeeSendingDomain
    if (key === 'portal_domain') return canSeePortalDomain
    if (key === 'email_calendar') return canSeeEmailCalendar
    if (key === 'migration') return canSeeMigration
    return true
  }

  const fieldClass = 'flex flex-col gap-1.5'
  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
  const valueClass = 'text-[13px] text-brand dark:text-[#EDEEF0]'
  const inputClass =
    'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'

  return (
    <AppShell>
      <div className="flex h-full">
        {/* Left nav panel */}
        <div
          className="flex flex-col flex-shrink-0 bg-surface-card dark:bg-[#383838] h-full border-r border-[#C8CDD6] dark:border-[#484848]"
          style={{ width: '200px', borderRightWidth: '0.5px' }}
        >
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 h-12 px-4 border-b border-[#C8CDD6] dark:border-[#484848] hover:bg-surface-page dark:hover:bg-dark-page transition-colors flex-shrink-0 w-full"
            style={{ borderBottomWidth: '0.5px' }}
          >
            <ChevronLeft className="h-4 w-4 text-brand dark:text-[#4A7FA5]" />
            <span className="text-[13px] font-medium text-brand dark:text-[#4A7FA5]">Settings</span>
          </button>
          <div className="flex flex-col overflow-y-auto flex-1">
            {SECTIONS.map((section) => {
              const visibleTabs = TABS.filter(
                (tab) => section.keys.includes(tab.key) && isTabVisible(tab.key)
              )
              if (visibleTabs.length === 0) return null
              return (
                <div key={section.label} className="border-t border-[#D5D8DE] dark:border-[#484848] mt-1 first:border-t-0 first:mt-0">
                  <div className="flex items-center gap-2 px-3 pt-2 pb-1">
                    <div className="h-px flex-1 bg-[#D5D8DE] dark:bg-[#484848]" />
                    <span className="text-[10px] font-semibold text-[#6B7280] dark:text-[#6B7280] whitespace-nowrap">
                      {section.label}
                    </span>
                    <div className="h-px flex-1 bg-[#D5D8DE] dark:bg-[#484848]" />
                  </div>
                  {visibleTabs.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={cn(
                        'w-full text-left h-9 px-4 text-[13px] transition-colors',
                        activeTab === tab.key
                          ? 'text-brand dark:text-[#4A7FA5] font-medium bg-white/30 dark:bg-white/10 border-l-2 border-[#1F3148] dark:border-[#4A7FA5]'
                          : 'text-[#4B5563] dark:text-[#C4C9D4] hover:text-brand dark:hover:text-[#EDEEF0] hover:bg-[#E4E6EA] dark:hover:bg-[#2D2D2D]'
                      )}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">

          <div>
            <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Settings</h1>
            <p className="text-[12px] text-[#6B7280] mt-0.5">
              Manage your profile and firm configuration.
            </p>
          </div>

          {/* My Integrations tab */}
        {activeTab === 'my_integrations' && <MyIntegrationsTabContent />}

        {/* Profile tab */}
        {activeTab === 'profile' && (
          <>
            <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-4 max-w-lg">
              <div className={fieldClass}>
                <span className={labelClass}>Full name</span>
                <span className={valueClass}>{user?.full_name ?? '—'}</span>
              </div>
              <div className={fieldClass}>
                <span className={labelClass}>Email</span>
                <span className={valueClass}>{user?.email ?? '—'}</span>
              </div>
              <div className={fieldClass}>
                <span className={labelClass}>Role</span>
                <span
                  className="w-fit bg-[#E5E7EB] text-brand text-[11px] font-medium px-2 py-0.5 rounded-full"
                  style={{ borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'inherit' }}
                >
                  {user?.role ? formatRoleLabel(user.role) : '—'}
                </span>
              </div>
              <div className={fieldClass}>
                <span className={labelClass}>Two-factor authentication</span>
                {user?.totp_enabled ? (
                  <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
                    Enabled
                  </span>
                ) : (
                  <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#E5E7EB] text-[#6B7280]">
                    Not enabled
                  </span>
                )}
              </div>
            </div>
            {isFirmOwner && (
              <p className="text-[11px] text-[#6B7280]" style={{ marginTop: '8px' }}>
                To update your profile details, contact your JAMM PX administrator.
              </p>
            )}
          </>
        )}

        {/* Firm tab */}
        {activeTab === 'firm' && (
          <>
            <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-4 max-w-lg">
              {firmLoading ? (
                <>
                  <div className="h-3 w-[120px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-3 w-[120px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-3 w-[120px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </>
              ) : (
                <>
                  <div className={fieldClass}>
                    <span className={labelClass}>Firm name</span>
                    <span className={valueClass}>{firmData?.name ?? '—'}</span>
                  </div>
                  <div className={fieldClass}>
                    <span className={labelClass}>Slug</span>
                    <span className={valueClass}>{firmData?.slug ?? '—'}</span>
                    <span className="text-[11px] text-[#6B7280]">
                      Your firm&apos;s unique identifier in client portal URLs.
                    </span>
                  </div>
                  <div className={fieldClass}>
                    <span className={labelClass}>Subscription plan</span>
                    <span
                      className="w-fit bg-[#E5E7EB] text-brand text-[11px] font-medium px-2 py-0.5 rounded-full"
                      style={{ borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'inherit' }}
                    >
                      {firmData?.subscription_tier
                        ? firmData.subscription_tier.charAt(0).toUpperCase() +
                          firmData.subscription_tier.slice(1)
                        : 'Trial'}
                    </span>
                  </div>
                  <div className={fieldClass}>
                    <span className={labelClass}>Member since</span>
                    <span className={valueClass}>
                      {firmData?.created_at
                        ? new Date(firmData.created_at).getFullYear()
                        : '—'}
                    </span>
                  </div>
                  <div className={fieldClass}>
                    <span className={labelClass}>Status</span>
                    {firmData?.is_active === true ? (
                      <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
                        Active
                      </span>
                    ) : (
                      <span className="w-fit text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#FEE2E2] text-[#991B1B]">
                        Inactive
                      </span>
                    )}
                  </div>
                </>
              )}
            </div>
            {isFirmOwner && (
              <p className="text-[11px] text-[#6B7280]" style={{ marginTop: '8px' }}>
                To update firm details or change your subscription, contact JAMM PX support.
              </p>
            )}

            {/* Timesheets section */}
            {isFirmOwner && (
              <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-3 max-w-lg" style={{ marginTop: '12px' }}>
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Timesheets</p>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-[13px] text-brand dark:text-[#EDEEF0]">
                      Require manager approval for submitted timesheets
                    </p>
                    <p className="text-[11px] text-[#6B7280] mt-0.5">
                      When on, submitted entries show as Pending Approval until a manager approves them.
                    </p>
                  </div>
                  <button
                    onClick={handleToggleApproval}
                    disabled={savingApproval || approvalRequired === null}
                    className={cn(
                      'relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors focus:outline-none disabled:opacity-60',
                      approvalRequired ? 'bg-brand dark:bg-brand-btn' : 'bg-[#D1D5DB]'
                    )}
                    aria-label="Toggle approval requirement"
                  >
                    <span
                      className={cn(
                        'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
                        approvalRequired ? 'translate-x-[18px]' : 'translate-x-0.5'
                      )}
                      style={{ marginTop: '2px' }}
                    />
                  </button>
                </div>
              </div>
            )}

            {/* Email Settings section */}
            {isFirmOwner && (
              <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-3 max-w-lg" style={{ marginTop: '12px' }}>
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Email Settings</p>
                <div className={fieldClass}>
                  <label className={labelClass}>Reply-To Email Address</label>
                  <input
                    type="email"
                    value={emailReplyTo}
                    onChange={(e) => setEmailReplyTo(e.target.value)}
                    placeholder="owner@yourfirm.com"
                    className={inputClass}
                  />
                  <span className="text-[11px] text-[#6B7280]">
                    When clients reply to emails from JAMM PX, their reply goes to this address.
                  </span>
                </div>
                <div className={fieldClass}>
                  <label className={labelClass}>Email Display Name</label>
                  <input
                    type="text"
                    value={emailDisplayName}
                    onChange={(e) => setEmailDisplayName(e.target.value)}
                    placeholder={firmData?.name ?? 'Your firm name'}
                    className={inputClass}
                  />
                  <span className="text-[11px] text-[#6B7280]">
                    The name clients see in their inbox. Defaults to your firm name.
                  </span>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveEmailSettings}
                    disabled={savingEmail}
                    className="h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60"
                  >
                    {savingEmail ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {/* Review Requests section */}
            {isFirmOwner && (
              <div className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-3 max-w-lg" style={{ marginTop: '12px' }}>
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Review Requests</p>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="text-[13px] text-brand dark:text-[#EDEEF0]">Enable review requests</p>
                    <p className="text-[11px] text-[#6B7280] mt-0.5">
                      When enabled, clients who rate their experience 9 or 10 will be prompted to leave a Google review after an engagement is marked complete.
                    </p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={reviewEnabled}
                    onClick={() => setReviewEnabled((v) => !v)}
                    className={cn(
                      'relative w-9 h-5 rounded-full transition-colors flex-shrink-0 overflow-hidden',
                      reviewEnabled ? 'bg-brand dark:bg-brand-btn' : 'bg-[#D1D5DB]',
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-[3px] left-[3px] w-3.5 h-3.5 rounded-full bg-white shadow transition-transform',
                        reviewEnabled ? 'translate-x-[16px]' : 'translate-x-0',
                      )}
                    />
                  </button>
                </div>
                <div className={fieldClass}>
                  <label className={labelClass}>Google Review Link</label>
                  <input
                    type="text"
                    value={googleReviewUrl}
                    onChange={(e) => setGoogleReviewUrl(e.target.value)}
                    placeholder="https://g.page/r/your-business/review"
                    className={inputClass}
                  />
                  <span className="text-[11px] text-[#6B7280]">
                    Clients who rate their experience 9 or 10 will be directed here to leave a public review.
                  </span>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveReviewSettings}
                    disabled={savingReview}
                    className="h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60"
                  >
                    {savingReview ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {/* Data export section */}
            {isFirmOwner && (
              <DataExportSection />
            )}
          </>
        )}

        {/* Team tab */}
        {activeTab === 'team' && (
          <>
            {teamLoading ? (
              <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex gap-2 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
                  >
                    <div className="h-2 w-[40%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                    <div className="h-2 w-[60%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                    <div className="h-2 w-[30%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                    <div className="h-4 w-[72px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full" />
                  </div>
                ))}
              </div>
            ) : team.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                  <span className="text-[18px]">👥</span>
                </div>
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                  No team members yet
                </p>
                <p className="text-[12px] text-[#6B7280]">
                  Invite staff to your firm to see them here.
                </p>
              </div>
            ) : (
              <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-surface-card dark:bg-[#252525]">
                      {['Name', 'Email', 'Role', 'Status'].map((col) => (
                        <th
                          key={col}
                          className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {team.map((member, i) => (
                      <tr
                        key={member.id}
                        className={cn(
                          'bg-surface-page dark:bg-dark-page',
                          i !== team.length - 1
                            ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                            : '',
                        )}
                      >
                        <td className="px-4 py-3">
                          <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                            {member.full_name ?? '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                            {member.email}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <RoleBadge role={member.role} />
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              'text-[11px] font-medium px-2 py-0.5 rounded-full',
                              member.is_active !== false
                                ? 'bg-[#D1FAE5] text-[#065F46]'
                                : 'bg-[#E5E7EB] text-[#6B7280]',
                            )}
                          >
                            {member.is_active !== false ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {isFirmOwner && (
              <div
                ref={inviteFormRef}
                className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border dark:border-dark-border p-4 max-w-lg"
                style={{ borderWidth: '0.5px', marginTop: '16px' }}
              >
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                  Invite Team Member
                </p>
                <p className="text-[12px] text-[#6B7280] mt-1">
                  Add a new staff member to your firm. They will be able to log in immediately
                  with the credentials you set.
                </p>
                <form onSubmit={handleInvite} className="flex flex-col gap-3 mt-4">
                  <div className={fieldClass}>
                    <label className={labelClass}>Full name</label>
                    <input
                      type="text"
                      required
                      autoComplete="off"
                      value={inviteFullName}
                      onChange={(e) => { setFormDirty(true); setInviteFullName(e.target.value) }}
                      className={inputClass}
                    />
                  </div>
                  <div className={fieldClass}>
                    <label className={labelClass}>Email address</label>
                    <input
                      type="email"
                      required
                      autoComplete="off"
                      value={inviteEmail}
                      onChange={(e) => { setFormDirty(true); setInviteEmail(e.target.value) }}
                      className={inputClass}
                    />
                  </div>
                  <div className={fieldClass}>
                    <label className={labelClass}>Temporary password</label>
                    <div className="relative">
                      <input
                        type={showInvitePassword || invitePasswordLocked ? 'text' : 'password'}
                        required
                        autoComplete="new-password"
                        value={invitePassword}
                        onChange={(e) => { setFormDirty(true); setInvitePassword(e.target.value) }}
                        className={inputClass}
                      />
                      <button
                        type="button"
                        onClick={() => setInvitePasswordLocked((prev) => !prev)}
                        onMouseEnter={() => setShowInvitePassword(true)}
                        onMouseLeave={() => setShowInvitePassword(false)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-brand transition-colors"
                      >
                        {invitePasswordLocked || showInvitePassword ? (
                          <EyeOff style={{ width: 14, height: 14 }} />
                        ) : (
                          <Eye style={{ width: 14, height: 14 }} />
                        )}
                      </button>
                    </div>
                    <span className="text-[11px] text-[#6B7280]">
                      They can change this after first login.
                    </span>
                  </div>
                  <div className={fieldClass}>
                    <label className={labelClass}>Role</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value as 'staff' | 'manager' | 'firm_owner')}
                      className={inputClass}
                    >
                      <option value="firm_owner">Partner</option>
                      <option value="staff">Staff</option>
                      <option value="manager">Manager</option>
                    </select>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={inviteSubmitting}
                      className="h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60"
                    >
                      {inviteSubmitting ? 'Adding...' : '+ Add Team Member'}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </>
        )}

        {/* Security tab */}
        {activeTab === 'security' && canSeeSecurity && <SecurityTab />}

        {/* Automations tab */}
        {activeTab === 'automations' && canSeeAutomations && <AutomationsTab />}

        {/* Fee Schedule tab */}
        {activeTab === 'fee_schedule' && (
          <FeeScheduleTab
            firmSettings={firmData?.settings ?? null}
            onSaved={() => { /* firmData will refetch on next focus */ }}
          />
        )}

        {/* Portal Branding tab */}
        {activeTab === 'portal_branding' && isFirmOwner && <PortalBrandingTab />}

        {/* Email Domain tab */}
        {activeTab === 'sending_domain' && canSeeSendingDomain && <SendingDomainTab />}

        {/* Portal Domain tab */}
        {activeTab === 'portal_domain' && canSeePortalDomain && <PortalDomainTab />}

        {/* Email & Calendar tab */}
        {activeTab === 'email_calendar' && canSeeEmailCalendar && <EmailCalendarTab />}

          {/* Migration tab */}
          {activeTab === 'migration' && canSeeMigration && <MigrationTab />}

        </div>
      </div>
    </AppShell>
  )
}
