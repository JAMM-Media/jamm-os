// frontend/src/components/ui/Tabs.tsx
'use client'

import { cn } from '@/lib/utils'

interface Tab {
  key: string
  label: string
}

interface TabsProps {
  tabs: Tab[]
  active: string
  onChange: (key: string) => void
}

export function Tabs({ tabs, active, onChange }: TabsProps) {
  return (
    <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border mb-6">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            'px-4 py-2.5 text-[13px] transition-colors relative',
            active === tab.key
              ? 'text-brand dark:text-[#4A7FA5] font-medium'
              : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal'
          )}
        >
          {tab.label}
          {active === tab.key && (
            <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand dark:bg-[#4A7FA5]" />
          )}
        </button>
      ))}
    </div>
  )
}
