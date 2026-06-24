// frontend/src/components/staff/StaffCredentials.tsx
'use client'

import { useState, useCallback } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { useFetch } from '@/lib/hooks/useFetch'
import { staffApi, type StaffCredential, type CPERecord, type StaffMember } from '@/lib/api/staffApi'
import { CredentialModal } from '@/components/staff/CredentialModal'
import { CPEModal } from '@/components/staff/CPEModal'

const CREDENTIAL_TYPE_LABELS: Record<string, string> = {
  cpa_license: 'CPA License',
  ea_enrollment: 'EA Enrollment',
  ptin: 'PTIN',
  state_license: 'State License',
  other: 'Other',
}

const CPE_STATUS_LABELS: Record<string, string> = {
  in_progress: 'In Progress',
  complete: 'Complete',
  overdue: 'Overdue',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatPeriod(start: string, end: string): string {
  const s = new Date(start)
  const e = new Date(end)
  const fmt = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
  return `${fmt(s)} - ${fmt(e)}`
}

function CredentialStatusBadge({ cred }: { cred: StaffCredential }) {
  if (!cred.expires_at) return null
  const today = new Date()
  const expiry = new Date(cred.expires_at)
  if (expiry < today) {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#FEE2E2] text-[#991B1B] text-[11px] font-medium">
        Expired
      </span>
    )
  }
  if (cred.is_expiring_soon) {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#FEF3C7] text-[#92400E] text-[11px] font-medium">
        Expiring Soon
      </span>
    )
  }
  return (
    <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#D1FAE5] text-[#065F46] text-[11px] font-medium">
      Active
    </span>
  )
}

function CPEStatusBadge({ status }: { status: string }) {
  if (status === 'complete') {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#D1FAE5] text-[#065F46] text-[11px] font-medium">
        Complete
      </span>
    )
  }
  if (status === 'overdue') {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#FEE2E2] text-[#991B1B] text-[11px] font-medium">
        Overdue
      </span>
    )
  }
  return (
    <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#DBEAFE] text-[#1E40AF] text-[11px] font-medium">
      In Progress
    </span>
  )
}

function staffName(staff: StaffMember[], userId: string): string {
  const s = staff.find((m) => m.id === userId)
  return s ? (s.full_name || s.email) : userId
}

const thClass = 'text-[11px] font-medium uppercase tracking-[0.05em] text-[#6B7280] px-4 py-2.5'
const tdClass = 'px-4 py-3 text-[12px]'

export function StaffCredentials() {
  const [credTick, setCredTick] = useState(0)
  const [cpeTick, setCpeTick] = useState(0)
  const [credentialModalOpen, setCredentialModalOpen] = useState(false)
  const [cpeModalOpen, setCpeModalOpen] = useState(false)
  const [editingCredential, setEditingCredential] = useState<StaffCredential | null>(null)
  const [editingCPE, setEditingCPE] = useState<CPERecord | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [confirmDeleteCPEId, setConfirmDeleteCPEId] = useState<string | null>(null)

  const { data: credData, isLoading: credLoading } = useFetch(
    () => staffApi.listCredentials(),
    [credTick]
  )
  const { data: cpeData, isLoading: cpeLoading } = useFetch(
    () => staffApi.listCPERecords(),
    [cpeTick]
  )
  const { data: staffData } = useFetch(() => staffApi.listStaff(), [])

  const credentials: StaffCredential[] = credData?.items ?? []
  const cpeRecords: CPERecord[] = cpeData?.items ?? []
  const staff: StaffMember[] = staffData ?? []

  const handleCredSaved = useCallback(() => setCredTick((t) => t + 1), [])
  const handleCpeSaved = useCallback(() => setCpeTick((t) => t + 1), [])

  async function handleDeleteCred(id: string) {
    try {
      await staffApi.deleteCredential(id)
      setConfirmDeleteId(null)
      setCredTick((t) => t + 1)
    } catch {
      // silently ignore
    }
  }

  async function handleDeleteCPE(id: string) {
    try {
      await staffApi.deleteCPERecord(id)
      setConfirmDeleteCPEId(null)
      setCpeTick((t) => t + 1)
    } catch {
      // silently ignore
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {/* Credentials Section */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">Credentials</span>
          <button
            onClick={() => { setEditingCredential(null); setCredentialModalOpen(true) }}
            className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
          >
            + Add
          </button>
        </div>

        <div className="rounded-[10px] border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-[#EDEEF0] dark:bg-[#252525]">
                {['Staff Member', 'Type', 'Number', 'State', 'Issued', 'Expires', 'Status', 'Actions'].map((col) => (
                  <th key={col} className={thClass + ' text-left'}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {credLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card">
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className={tdClass}>
                        <div className="h-2 w-[60%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : credentials.length === 0 ? (
                <tr className="bg-[#E4E6EA] dark:bg-[#2D2D2D]">
                  <td colSpan={8} className="px-4 py-8 text-center text-[12px] text-[#6B7280]">
                    No credentials on file. Add a credential to track license and registration expiries.
                  </td>
                </tr>
              ) : (
                credentials.map((cred) => (
                  <>
                    <tr
                      key={cred.id}
                      className="bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card hover:bg-[#D5D8DE] dark:hover:bg-[#333333] transition-colors"
                    >
                      <td className={tdClass}>
                        <span className="font-medium text-brand dark:text-[#EDEEF0]">
                          {staffName(staff, cred.user_id)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {CREDENTIAL_TYPE_LABELS[cred.credential_type] ?? cred.credential_type}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#6B7280] dark:text-[#9CA3AF]">
                          {cred.credential_number || '-'}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#6B7280] dark:text-[#9CA3AF]">
                          {cred.state || '-'}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {formatDate(cred.issued_at)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {formatDate(cred.expires_at)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <CredentialStatusBadge cred={cred} />
                      </td>
                      <td className={tdClass}>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => { setEditingCredential(cred); setCredentialModalOpen(true) }}
                            className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
                            title="Edit"
                          >
                            <Pencil className="h-[14px] w-[14px]" />
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(cred.id)}
                            className="text-[#6B7280] hover:text-[#991B1B] transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="h-[14px] w-[14px]" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {confirmDeleteId === cred.id && (
                      <tr key={cred.id + '-confirm'} className="bg-[#FEE2E2] dark:bg-[#3D2525]">
                        <td colSpan={8} className="px-4 py-2.5">
                          <div className="flex items-center gap-3">
                            <span className="text-[12px] text-[#991B1B]">Delete this credential?</span>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="text-[12px] text-[#6B7280] hover:text-brand underline"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleDeleteCred(cred.id)}
                              className="h-7 px-3 rounded-[6px] bg-[#DC2626] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
                            >
                              Confirm
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* CPE Records Section */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">CPE Records</span>
          <button
            onClick={() => { setEditingCPE(null); setCpeModalOpen(true) }}
            className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
          >
            + Add
          </button>
        </div>

        <div className="rounded-[10px] border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-[#EDEEF0] dark:bg-[#252525]">
                {['Staff Member', 'Period', 'Required Hrs', 'Completed Hrs', 'Remaining Hrs', 'Deadline', 'Status', 'Actions'].map((col) => (
                  <th key={col} className={thClass + ' text-left'}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cpeLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card">
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className={tdClass}>
                        <div className="h-2 w-[60%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : cpeRecords.length === 0 ? (
                <tr className="bg-[#E4E6EA] dark:bg-[#2D2D2D]">
                  <td colSpan={8} className="px-4 py-8 text-center text-[12px] text-[#6B7280]">
                    No CPE records on file. Add a record to track continuing education requirements.
                  </td>
                </tr>
              ) : (
                cpeRecords.map((rec) => (
                  <>
                    <tr
                      key={rec.id}
                      className="bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card hover:bg-[#D5D8DE] dark:hover:bg-[#333333] transition-colors"
                    >
                      <td className={tdClass}>
                        <span className="font-medium text-brand dark:text-[#EDEEF0]">
                          {staffName(staff, rec.user_id)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {formatPeriod(rec.reporting_period_start, rec.reporting_period_end)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {rec.hours_required.toFixed(1)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {rec.hours_completed.toFixed(1)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {rec.hours_remaining.toFixed(1)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <span className="text-[#374151] dark:text-[#9CA3AF]">
                          {formatDate(rec.deadline)}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <CPEStatusBadge status={rec.status} />
                      </td>
                      <td className={tdClass}>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => { setEditingCPE(rec); setCpeModalOpen(true) }}
                            className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
                            title="Edit"
                          >
                            <Pencil className="h-[14px] w-[14px]" />
                          </button>
                          <button
                            onClick={() => setConfirmDeleteCPEId(rec.id)}
                            className="text-[#6B7280] hover:text-[#991B1B] transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="h-[14px] w-[14px]" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {confirmDeleteCPEId === rec.id && (
                      <tr key={rec.id + '-confirm'} className="bg-[#FEE2E2] dark:bg-[#3D2525]">
                        <td colSpan={8} className="px-4 py-2.5">
                          <div className="flex items-center gap-3">
                            <span className="text-[12px] text-[#991B1B]">Delete this record?</span>
                            <button
                              onClick={() => setConfirmDeleteCPEId(null)}
                              className="text-[12px] text-[#6B7280] hover:text-brand underline"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleDeleteCPE(rec.id)}
                              className="h-7 px-3 rounded-[6px] bg-[#DC2626] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
                            >
                              Confirm
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <CredentialModal
        open={credentialModalOpen}
        onClose={() => { setCredentialModalOpen(false); setEditingCredential(null) }}
        onSaved={handleCredSaved}
        staff={staff}
        editing={editingCredential}
      />

      <CPEModal
        open={cpeModalOpen}
        onClose={() => { setCpeModalOpen(false); setEditingCPE(null) }}
        onSaved={handleCpeSaved}
        staff={staff}
        editing={editingCPE}
      />
    </div>
  )
}
