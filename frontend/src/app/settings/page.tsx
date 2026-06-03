// frontend/src/app/settings/page.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import { Eye, EyeOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import api from '@/lib/api'
import { settingsApi, type FirmDetails, type StaffMember } from '@/lib/api/settingsApi'
import AutomationsTab from '@/components/settings/AutomationsTab'
import SecurityTab from '@/components/settings/SecurityTab'
import FeeScheduleTab from '@/components/settings/FeeScheduleTab'
import PortalBrandingTab from '@/components/settings/PortalBrandingTab'
import { onConciergeAction, setFormDirty } from '@/lib/events/conciergeEvents'

const TABS = [
  { key: 'profile', label: 'Profile' },
  { key: 'firm', label: 'Firm' },
  { key: 'team', label: 'Team' },
  { key: 'security', label: 'Security' },
  { key: 'automations', label: 'Automations' },
  { key: 'fee_schedule', label: 'Fee Schedule' },
  { key: 'portal_branding', label: 'Portal' },
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

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile')
  const { user } = useAuth()
  const [approvalRequired, setApprovalRequired] = useState<boolean | null>(null)
  const [savingApproval, setSavingApproval] = useState(false)

  const [emailReplyTo, setEmailReplyTo] = useState('')
  const [emailDisplayName, setEmailDisplayName] = useState('')
  const [savingEmail, setSavingEmail] = useState(false)

  const [googleReviewUrl, setGoogleReviewUrl] = useState('')
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
  const [inviteRole, setInviteRole] = useState<'staff' | 'manager'>('staff')
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
        setTimeout(() => inviteFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150)
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
          inviteFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
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

  const fieldClass = 'flex flex-col gap-1.5'
  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
  const valueClass = 'text-[13px] text-brand dark:text-[#EDEEF0]'
  const inputClass =
    'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'

  return (
    <AppShell>
      <div className="p-6 flex flex-col gap-6">

        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Settings</h1>
          <p className="text-[12px] text-[#6B7280] mt-0.5">
            Manage your profile and firm configuration.
          </p>
        </div>

        {/* Tab bar */}
        <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border">
          {TABS.filter((tab) => {
            if (tab.key === 'automations') return canSeeAutomations
            if (tab.key === 'security') return canSeeSecurity
            if (tab.key === 'fee_schedule') return isFirmOwner
            if (tab.key === 'portal_branding') return isFirmOwner
            return true
          }).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'px-4 py-2.5 text-[13px] transition-colors relative',
                activeTab === tab.key
                  ? 'text-brand dark:text-[#4A7FA5] font-medium'
                  : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal',
              )}
            >
              {tab.label}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand dark:bg-[#4A7FA5]" />
              )}
            </button>
          ))}
        </div>

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
                      onChange={(e) => setInviteRole(e.target.value as 'staff' | 'manager')}
                      className={inputClass}
                    >
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


      </div>
    </AppShell>
  )
}
