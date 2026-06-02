// frontend/src/components/layout/AppShell.tsx
'use client'

import { useState } from 'react'
import { Sidebar } from './Sidebar'
import { ConciergePanel } from '@/components/concierge/ConciergePanel'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [conciergeOpen, setConciergeOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('jamm_concierge_open') === 'true'
    }
    return false
  })

  function handleConciergeOpen() {
    sessionStorage.setItem('jamm_concierge_open', 'true')
    setConciergeOpen(true)
  }

  function handleConciergeClose() {
    sessionStorage.removeItem('jamm_concierge_open')
    setConciergeOpen(false)
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface-page dark:bg-dark-page">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        onConciergeOpen={handleConciergeOpen}
      />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
      <ConciergePanel isOpen={conciergeOpen} onClose={handleConciergeClose} />
    </div>
  )
}
