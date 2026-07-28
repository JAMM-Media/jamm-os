// frontend/src/components/layout/AppShell.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { onConciergeAction } from '@/lib/events/conciergeEvents'
import { Sidebar } from './Sidebar'
import { ConciergePanel } from '@/components/concierge/ConciergePanel'
import { PersistentEntryButton } from '@/components/concierge-inline/PersistentEntryButton'
import { useConciergeNotifications } from '@/lib/hooks/useConciergeNotifications'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('jamm_sidebar_collapsed') === 'true'
    }
    return false
  })
  const pathname = usePathname()
  const isSettingsRoute = pathname.startsWith('/settings')
  const mainRef = useRef<HTMLDivElement>(null)
  // Always initialize to false so server and client render identically on
  // first paint (avoids a hydration mismatch). Restore the persisted value
  // from sessionStorage AFTER mount instead, inside an effect -- this is the
  // standard SSR-safe pattern for state that depends on browser-only storage.
  const [conciergeOpen, setConciergeOpen] = useState(false)
  const [conciergePosition, setConciergePosition] = useState<'left' | 'right'>('right')
  const { notifications } = useConciergeNotifications()

  useEffect(() => {
    const saved = sessionStorage.getItem('jamm_concierge_open') === 'true'
    if (saved) setConciergeOpen(true)
  }, [])

  useEffect(() => {
    const main = mainRef.current
    if (!main) return
    const saved = sessionStorage.getItem(`jamm_scroll_${pathname}`)
    if (saved) {
      requestAnimationFrame(() => {
        main.scrollTop = parseInt(saved, 10)
      })
    }

    function handleScroll() {
      sessionStorage.setItem(`jamm_scroll_${pathname}`, String(main!.scrollTop))
    }
    main.addEventListener('scroll', handleScroll)
    return () => main.removeEventListener('scroll', handleScroll)
  }, [pathname])

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.type === 'open-panel') {
        sessionStorage.setItem('jamm_concierge_open', 'true')
        setConciergeOpen(true)
      }
    })
  }, [])

  useEffect(() => {
    const stored = localStorage.getItem('jamm_concierge_position') as 'left' | 'right' | null
    if (stored === 'left' || stored === 'right') setConciergePosition(stored)

    const handler = (e: Event) => {
      const pos = (e as CustomEvent<{ position: 'left' | 'right' }>).detail.position
      if (pos === 'left' || pos === 'right') setConciergePosition(pos)
    }
    window.addEventListener('jamm:concierge-position-changed', handler)
    return () => window.removeEventListener('jamm:concierge-position-changed', handler)
  }, [])

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
        collapsed={isSettingsRoute ? true : collapsed}
        onToggle={isSettingsRoute ? () => {} : () => setCollapsed((c) => {
          const next = !c
          localStorage.setItem('jamm_sidebar_collapsed', String(next))
          return next
        })}
        locked={isSettingsRoute}
      />
      <main ref={mainRef} className={`flex-1 overflow-y-auto transition-[padding] duration-200 ${conciergeOpen ? 'pr-[400px]' : ''}`}>
        {children}
      </main>
      <ConciergePanel isOpen={conciergeOpen} onClose={handleConciergeClose} />
      {/* Persistent Concierge entry -- fixed bottom-right, hidden when panel is open.
          hasSuggestion is false here because notification state lives inside ConciergePanel.
          Real notification-awareness wiring is a future task. */}
      {!conciergeOpen && (
        <div className={`fixed bottom-6 z-40 ${conciergePosition === 'left' ? 'left-6' : 'right-6'}`}>
          <PersistentEntryButton
            onClick={handleConciergeOpen}
            hasSuggestion={notifications.length > 0}
          />
        </div>
      )}
    </div>
  )
}
