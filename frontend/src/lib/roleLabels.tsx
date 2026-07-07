// frontend/src/lib/roleLabels.ts

export const ROLE_LABELS: Record<string, string> = {
  firm_owner: 'Owner',
  manager: 'Manager',
  staff: 'Staff',
}

export function formatRoleLabel(role: string): string {
  if (ROLE_LABELS[role]) return ROLE_LABELS[role]
  return role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function RoleBadge({ role }: { role: string }) {
  if (role === 'firm_owner') {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#1F3148] text-white text-[11px] font-medium">
        {ROLE_LABELS.firm_owner}
      </span>
    )
  }
  if (role === 'manager') {
    return (
      <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#DBEAFE] text-[#1E40AF] text-[11px] font-medium">
        {ROLE_LABELS.manager}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center h-[22px] px-2 rounded-full bg-[#E5E7EB] text-[#1F3148] border border-[0.5px] border-[#1F3148] text-[11px] font-medium">
      {formatRoleLabel(role)}
    </span>
  )
}
