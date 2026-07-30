// frontend/src/components/concierge-inline/PersistentEntryButton.tsx
'use client'

import { Sparkles } from 'lucide-react'

interface PersistentEntryButtonProps {
  onClick: () => void
  label?: string
  hasSuggestion?: boolean
}

export function PersistentEntryButton({ onClick, label = 'Ask Concierge', hasSuggestion = false }: PersistentEntryButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity shadow-sm ${hasSuggestion ? 'ring-2 ring-concierge' : ''}`}
    >
      <Sparkles className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}
