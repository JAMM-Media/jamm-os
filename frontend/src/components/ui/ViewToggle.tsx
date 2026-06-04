// frontend/src/components/ui/ViewToggle.tsx

import { LayoutGrid, List } from 'lucide-react'
import { cn } from '@/lib/utils'

type ViewMode = 'table' | 'card'

interface ViewToggleProps {
  value: ViewMode
  onChange: (value: ViewMode) => void
}

export function ViewToggle({ value, onChange }: ViewToggleProps) {
  return (
    <div className="flex items-center rounded overflow-hidden border border-surface-border dark:border-dark-border">
      <button
        onClick={() => onChange('table')}
        className={cn(
          'flex items-center justify-center w-8 h-9 transition-colors',
          value === 'table'
            ? 'bg-brand dark:bg-brand-btn text-white'
            : 'bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0]'
        )}
        aria-label="List view"
      >
        <List className="h-4 w-4" />
      </button>
      <button
        onClick={() => onChange('card')}
        className={cn(
          'flex items-center justify-center w-8 h-9 transition-colors',
          value === 'card'
            ? 'bg-brand dark:bg-brand-btn text-white'
            : 'bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0]'
        )}
        aria-label="Card view"
      >
        <LayoutGrid className="h-4 w-4" />
      </button>
    </div>
  )
}
