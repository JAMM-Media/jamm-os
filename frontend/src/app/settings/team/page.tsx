// frontend/src/app/settings/team/page.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { Pencil, UserX, UserCheck, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { useFetch } from '@/lib/hooks/useFetch'
import { useAuth } from '@/lib/hooks/useAuth'
import { staffApi, type StaffMember } from '@/lib/api/staffApi'
import { EditStaffModal } from '@/components/settings/EditStaffModal'
import { DeleteStaffModal } from '@/components/settings/DeleteStaffModal'
import { onConciergeAction } from '@/lib/events/conciergeEvents'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const labelClass = 'block text-[12px] font-medium text-brand dark:text-[#EDEEF0] mb-1'

function RoleBadge({ role }: { role: string }) {
  if (role === 'firm_owner') {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#1F3148] text-white text-[11px] font-medium">
        Owner
      </span>
    )
  }
  if (role === 'manager') {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#DBEAFE] text-[#1E40AF] text-[11px] font-medium">
        Manager
      </span>
    )
  }
  return (
    <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#E5E7EB] text-[#1F3148] border border-[0.5px] border-[#1F3148] text-[11px] font-medium">
      Staff
    </span>
  )
}

function StatusBadge({ active }: { active: boolean }) {
  if (active) {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#D1FAE5] text-[#065F46] text-[11px] font-medium">
        Active
      </span>
    )
  }
  return (
    <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#E5E7EB] text-[#6B7280] text-[11px] font-medium">
      Inactive
    </span>
  )
}

export default function SettingsTeamPage() {
  const { user } = useAuth()
  const inviteRef = useRef<HTMLDivElement>(null)

  // Invite form state
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('staff')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [inviteSuccess, setInviteSuccess] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)

  // Team list state
  const [editingMember, setEditingMember] = useState<StaffMember | null>(null)
  const [deletingMember, setDeletingMember] = useState<StaffMember | null>(null)

  const { data, isLoading, refetch } = useFetch(() => staffApi.listStaff(), [])
  const members: StaffMember[] = data ?? []

  // Concierge scroll-to-invite
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
        setTimeout(() => inviteRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100)
      }
    } catch {
      sessionStorage.removeItem('jamm_concierge_pending')
    }
  }, [])

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'invite-staff') {
        inviteRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }, [])

  if (user?.role !== 'firm_owner') {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[14px] text-[#6B7280]">
            You do not have permission to manage team members.
          </p>
        </div>
      </AppShell>
    )
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    setInviteError(null)
    setInviteSuccess(false)
    setSubmitting(true)
    try {
      await staffApi.inviteStaff({
        email,
        full_name: fullName || undefined,
        role,
        password,
      })
      setInviteSuccess(true)
      setFullName('')
      setEmail('')
      setRole('staff')
      setPassword('')
      refetch()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ?? 'Failed to add staff member.'
      setInviteError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggleActive(member: StaffMember) {
    try {
      await staffApi.updateUser(member.id, { is_active: !member.is_active })
      refetch()
      toast.success(member.is_active ? 'Staff member deactivated.' : 'Staff member reactivated.')
    } catch {
      toast.error('Failed to update status.')
    }
  }

  return (
    <AppShell>
      <div className="p-6 flex flex-col gap-6 max-w-3xl">

        {/* Breadcrumb */}
        <div className="flex items-center gap-2">
          <Link
            href="/settings"
            className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            Settings
          </Link>
          <span className="text-[12px] text-[#9CA3AF]">/</span>
          <span className="text-[12px] text-brand dark:text-[#EDEEF0]">Team</span>
        </div>

        <h1 className="text-[24px] font-medium text-brand dark:text-[#EDEEF0]">Team</h1>

        {/* Invite Staff Section */}
        <div
          ref={inviteRef}
          className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border p-5"
        >
          <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0] mb-1">
            Invite Staff Member
          </p>
          <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] mb-4">
            Add a new staff member to your firm. They will use the temporary password you set to log
            in and should change it immediately.
          </p>

          {inviteSuccess && (
            <div className="mb-4 px-3 py-2 bg-[#D1FAE5] rounded text-[12px] text-[#065F46]">
              Staff member added. They can now log in with the email and temporary password you set.
            </div>
          )}

          {inviteError && (
            <p className="mb-3 text-[12px] text-[#DC2626]">{inviteError}</p>
          )}

          <form onSubmit={handleInvite} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Smith"
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Email <span className="text-[#DC2626]">*</span></label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@firm.com"
                  required
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Role <span className="text-[#DC2626]">*</span></label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  required
                  className={inputClass}
                >
                  <option value="staff">Staff</option>
                  <option value="manager">Manager</option>
                  <option value="firm_owner">Firm Owner</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className={labelClass}>
                  Temporary Password <span className="text-[#DC2626]">*</span>
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Temporary password"
                  required
                  minLength={8}
                  className={inputClass}
                />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={submitting}
                className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {submitting ? 'Adding...' : '+ Add Staff Member'}
              </button>
            </div>
          </form>
        </div>

        {/* Team Members Section */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">
              Team Members
            </span>
            {!isLoading && (
              <span className="text-[13px] text-[#6B7280] dark:text-[#9CA3AF]">
                {members.length} {members.length === 1 ? 'member' : 'members'}
              </span>
            )}
          </div>

          <div className="rounded-[10px] border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[2fr_2fr_1fr_1fr_1fr] bg-[#EDEEF0] dark:bg-[#252525] px-4 py-2.5">
              {['Name', 'Email', 'Role', 'Status', 'Actions'].map((col) => (
                <span key={col} className="text-[11px] font-medium uppercase tracking-[0.05em] text-[#6B7280]">
                  {col}
                </span>
              ))}
            </div>

            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[2fr_2fr_1fr_1fr_1fr] gap-4 px-4 py-3 bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
                >
                  {Array.from({ length: 5 }).map((_, j) => (
                    <div key={j} className="h-2 w-[60%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  ))}
                </div>
              ))
            ) : members.length === 0 ? (
              <div className="flex items-center justify-center px-4 py-10 bg-[#E4E6EA] dark:bg-[#2D2D2D]">
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                  No team members found.
                </p>
              </div>
            ) : (
              members.map((member) => {
                const isCurrentUser = member.id === user?.id
                return (
                  <div
                    key={member.id}
                    className="grid grid-cols-[2fr_2fr_1fr_1fr_1fr] items-center px-4 py-3 bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0 hover:bg-[#D5D8DE] dark:hover:bg-[#333333] transition-colors"
                  >
                    {/* Name */}
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] truncate">
                        {member.full_name || (
                          <span className="text-[#6B7280] dark:text-[#9CA3AF]">{member.email}</span>
                        )}
                      </span>
                      {isCurrentUser && (
                        <span className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF] flex-shrink-0">
                          (you)
                        </span>
                      )}
                    </div>

                    {/* Email */}
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF] truncate">
                      {member.email}
                    </span>

                    {/* Role */}
                    <div>
                      <RoleBadge role={member.role} />
                    </div>

                    {/* Status */}
                    <div>
                      <StatusBadge active={member.is_active} />
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setEditingMember(member)}
                        title="Edit"
                        className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
                      >
                        <Pencil className="h-[14px] w-[14px]" />
                      </button>

                      {!isCurrentUser && (
                        <button
                          onClick={() => handleToggleActive(member)}
                          title={member.is_active ? 'Deactivate' : 'Reactivate'}
                          className="text-[#6B7280] hover:text-[#92400E] transition-colors"
                        >
                          {member.is_active ? (
                            <UserX className="h-[14px] w-[14px]" />
                          ) : (
                            <UserCheck className="h-[14px] w-[14px]" />
                          )}
                        </button>
                      )}

                      {!isCurrentUser && (
                        <button
                          onClick={() => setDeletingMember(member)}
                          title="Delete"
                          className="text-[#6B7280] hover:text-[#991B1B] transition-colors"
                        >
                          <Trash2 className="h-[14px] w-[14px]" />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>

      <EditStaffModal
        open={editingMember !== null}
        onClose={() => setEditingMember(null)}
        onSaved={() => { refetch(); setEditingMember(null) }}
        member={editingMember}
      />

      <DeleteStaffModal
        open={deletingMember !== null}
        onClose={() => setDeletingMember(null)}
        onDeleted={() => { refetch(); setDeletingMember(null) }}
        member={deletingMember}
      />
    </AppShell>
  )
}
