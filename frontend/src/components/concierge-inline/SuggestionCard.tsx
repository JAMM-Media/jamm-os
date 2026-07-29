// frontend/src/components/concierge-inline/SuggestionCard.tsx
'use client'

import { X } from 'lucide-react'

interface Notification {
  id: string
  trigger_type: string
  message: string
  created_at: string
  metadata?: Record<string, unknown> | null
}

interface SuggestionCardProps {
  notification: Notification
  honestLabel?: string
  actionLabel?: string
  onAction?: () => void
  onDismiss: () => void
}

export function SuggestionCard({
  notification,
  honestLabel = 'Might be worth a look',
  actionLabel,
  onAction,
  onDismiss,
}: SuggestionCardProps) {
  return (
    <div className="flex flex-col ring-1 ring-concierge/30 rounded-[8px] bg-surface-card dark:bg-dark-card overflow-hidden">
      <div className="px-3 py-2 border-b border-[0.5px] border-surface-border dark:border-dark-border flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-concierge flex-shrink-0" />
        <span className="text-[10px] font-semibold uppercase tracking-wide text-concierge flex-1">
          JAMM Concierge
        </span>
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="px-3 py-2.5 flex flex-col gap-2">
        <p className="text-[11px] text-muted-foreground">{honestLabel}</p>
        <p className="text-[13px] leading-[1.5] text-brand dark:text-foreground">
          {notification.message}
        </p>
        {actionLabel && onAction && (
          <button
            onClick={onAction}
            className="self-start text-[11px] font-normal px-2.5 py-1 rounded-[4px] border border-concierge/60 text-concierge hover:bg-concierge/10 transition-colors"
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  )
}
