// frontend/src/components/staff/StaffRoster.tsx
'use client'

import { CheckCircle2 } from 'lucide-react'
import { useFetch } from '@/lib/hooks/useFetch'
import { staffApi, type StaffMember } from '@/lib/api/staffApi'

function formatMonthYear(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

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

export function StaffRoster() {
  const { data, isLoading } = useFetch(() => staffApi.listStaff(), [])
  const members: StaffMember[] = data ?? []

  return (
    <div className="rounded-[10px] border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      {/* Header */}
      <div className="grid grid-cols-6 bg-[#EDEEF0] dark:bg-[#252525] px-4 py-2.5">
        {['Name', 'Email', 'Role', '2FA', 'Status', 'Member Since'].map((col) => (
          <span
            key={col}
            className="text-[11px] font-medium uppercase tracking-[0.05em] text-[#6B7280]"
          >
            {col}
          </span>
        ))}
      </div>

      {isLoading ? (
        Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="grid grid-cols-6 gap-4 px-4 py-3 bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
          >
            {Array.from({ length: 6 }).map((_, j) => (
              <div key={j} className="h-2 w-[60%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            ))}
          </div>
        ))
      ) : members.length === 0 ? (
        <div className="flex items-center justify-center px-4 py-10 bg-[#E4E6EA] dark:bg-[#2D2D2D]">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No staff members found.</p>
        </div>
      ) : (
        members.map((member) => (
          <div
            key={member.id}
            className="grid grid-cols-6 items-center px-4 py-3 bg-[#E4E6EA] dark:bg-[#2D2D2D] border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0 hover:bg-[#D5D8DE] dark:hover:bg-[#333333] transition-colors"
          >
            <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] truncate">
              {member.full_name || member.email}
            </span>
            <span className="text-[12px] font-normal text-[#374151] dark:text-[#9CA3AF] truncate">
              {member.email}
            </span>
            <div>
              <RoleBadge role={member.role} />
            </div>
            <div>
              {member.totp_enabled ? (
                <CheckCircle2 className="h-[14px] w-[14px] text-[#065F46]" />
              ) : (
                <span className="text-[12px] text-[#9CA3AF]">-</span>
              )}
            </div>
            <div>
              <StatusBadge active={member.is_active} />
            </div>
            <span className="text-[12px] font-normal text-[#374151] dark:text-[#9CA3AF]">
              {formatMonthYear(member.created_at)}
            </span>
          </div>
        ))
      )}
    </div>
  )
}
