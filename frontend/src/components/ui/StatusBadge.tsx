// frontend/src/components/ui/StatusBadge.tsx

import { cn } from '@/lib/utils'

export type BadgeVariant =
  | 'in-progress'
  | 'awaiting-docs'
  | 'complete'
  | 'overdue'
  | 'not-started'
  | 'active'
  | 'inactive'
  | 'uploaded'
  | 'pending'
  | 'pending_signature'
  | 'signed'
  | 'rejected'
  | 'draft'
  | 'sent'
  | 'paid'
  | 'planning'
  | 'in_progress'
  | 'awaiting_docs'
  | 'not_started'
  | 'cancelled'
  | 'todo'
  | 'completed'
  | 'archived'
  | 'in_review'
  | 'done'
  | 'identified'
  | 'contacted'
  | 'call_booked'
  | 'proposal'
  | 'won'
  | 'lost'

interface StatusBadgeProps {
  variant: BadgeVariant
  label?: string
  className?: string
}

const variantConfig: Record<BadgeVariant, { bg: string; text: string; border?: string; defaultLabel: string }> = {
  'in-progress': {
    bg: 'bg-status-blue',
    text: 'text-status-blue-text',
    defaultLabel: 'In Progress',
  },
  'awaiting-docs': {
    bg: 'bg-status-amber',
    text: 'text-status-amber-text',
    defaultLabel: 'Awaiting Docs',
  },
  complete: {
    bg: 'bg-status-green',
    text: 'text-status-green-text',
    defaultLabel: 'Complete',
  },
  overdue: {
    bg: 'bg-status-red',
    text: 'text-status-red-text',
    defaultLabel: 'Overdue',
  },
  'not-started': {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Not Started',
  },
  active: {
    bg: 'bg-status-blue',
    text: 'text-status-blue-text',
    defaultLabel: 'Active',
  },
  inactive: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Inactive',
  },
  uploaded: {
    bg: 'bg-status-blue',
    text: 'text-status-blue-text',
    defaultLabel: 'Uploaded',
  },
  pending: {
    bg: 'bg-status-amber',
    text: 'text-status-amber-text',
    defaultLabel: 'Pending',
  },
  pending_signature: {
    bg: 'bg-[#DBEAFE]',
    text: 'text-[#1E40AF]',
    defaultLabel: 'Pending Signature',
  },
  signed: {
    bg: 'bg-status-green',
    text: 'text-status-green-text',
    defaultLabel: 'Signed',
  },
  rejected: {
    bg: 'bg-status-red',
    text: 'text-status-red-text',
    defaultLabel: 'Rejected',
  },
  draft: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Draft',
  },
  sent: {
    bg: 'bg-status-blue',
    text: 'text-status-blue-text',
    defaultLabel: 'Sent',
  },
  paid: {
    bg: 'bg-status-green',
    text: 'text-status-green-text',
    defaultLabel: 'Paid',
  },
  planning: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Planning',
  },
  in_progress: {
    bg: 'bg-status-blue',
    text: 'text-status-blue-text',
    defaultLabel: 'In Progress',
  },
  awaiting_docs: {
    bg: 'bg-status-amber',
    text: 'text-status-amber-text',
    defaultLabel: 'Awaiting Docs',
  },
  not_started: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Not Started',
  },
  cancelled: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Cancelled',
  },
  todo: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'To Do',
  },
  completed: {
    bg: 'bg-status-green',
    text: 'text-status-green-text',
    defaultLabel: 'Completed',
  },
  archived: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-[#6B7280]',
    border: 'border border-[0.5px] border-[#C8CDD6]',
    defaultLabel: 'Archived',
  },
  in_review: {
    bg: 'bg-status-amber',
    text: 'text-status-amber-text',
    defaultLabel: 'In Review',
  },
  done: {
    bg: 'bg-status-green',
    text: 'text-status-green-text',
    defaultLabel: 'Done',
  },
  identified: {
    bg: 'bg-[#E5E7EB]',
    text: 'text-brand',
    border: 'border border-[0.5px] border-brand',
    defaultLabel: 'Identified',
  },
  contacted: {
    bg: 'bg-status-amber',
    text: 'text-status-amber-text',
    defaultLabel: 'Contacted',
  },
  call_booked: {
    bg: 'bg-status-blue',
    text: 'text-status-blue-text',
    defaultLabel: 'Call Booked',
  },
  proposal: {
    bg: 'bg-[#DBEAFE]',
    text: 'text-[#1E40AF]',
    defaultLabel: 'Proposal',
  },
  won: {
    bg: 'bg-status-green',
    text: 'text-status-green-text',
    defaultLabel: 'Won',
  },
  lost: {
    bg: 'bg-status-red',
    text: 'text-status-red-text',
    defaultLabel: 'Lost',
  },
}

const FALLBACK_CONFIG = {
  bg: 'bg-[#E5E7EB]',
  text: 'text-brand',
  border: 'border border-[0.5px] border-brand',
  defaultLabel: 'Unknown',
}

export function StatusBadge({ variant, label, className }: StatusBadgeProps) {
  const config = variantConfig[variant] ?? FALLBACK_CONFIG
  return (
    <span
      className={cn(
        'inline-flex items-center h-[22px] px-2.5 rounded-badge text-[11px] font-medium whitespace-nowrap',
        config.bg,
        config.text,
        config.border,
        className
      )}
    >
      {label ?? config.defaultLabel}
    </span>
  )
}
