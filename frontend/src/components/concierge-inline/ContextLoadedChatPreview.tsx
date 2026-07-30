// frontend/src/components/concierge-inline/ContextLoadedChatPreview.tsx
'use client'

import { ArrowUpRight } from 'lucide-react'

interface ContextLoadedChatPreviewProps {
  openedFromLabel: string
}

export function ContextLoadedChatPreview({ openedFromLabel }: ContextLoadedChatPreviewProps) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-2 bg-surface-card dark:bg-dark-card border-b border-[0.5px] border-surface-border dark:border-dark-border">
      <ArrowUpRight className="h-3 w-3 text-concierge flex-shrink-0" />
      <span className="text-[11px] text-concierge font-semibold uppercase tracking-wide">
        opened from:
      </span>
      <span className="text-[11px] text-muted-foreground">
        {openedFromLabel}
      </span>
    </div>
  )
}
