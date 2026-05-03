// frontend/src/components/clients/ClientEmptyState.tsx

import { Users } from 'lucide-react'

interface ClientEmptyStateProps {
  onNewClient: () => void
}

export function ClientEmptyState({ onNewClient }: ClientEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 py-24 gap-[10px]">
      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
        <Users className="h-[18px] w-[18px] text-[#6B7280]" />
      </div>
      <div className="text-center">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-[3px]">
          No clients yet
        </p>
        <p className="text-[12px] text-[#6B7280]">
          Add your first client to get started.
        </p>
      </div>
      <button
        onClick={onNewClient}
        className="mt-1 px-3 h-9 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
      >
        + New Client
      </button>
    </div>
  )
}
