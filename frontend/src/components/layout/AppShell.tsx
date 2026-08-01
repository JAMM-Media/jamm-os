// frontend/src/components/layout/AppShell.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { onConciergeAction } from '@/lib/events/conciergeEvents'
import { useAuth } from '@/lib/hooks/useAuth'
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
  const [conciergeEntryMode, setConciergeEntryMode] = useState<'sidebar' | 'floating'>('floating')
  const { notifications } = useConciergeNotifications()
  const { user } = useAuth()

  // Draggable floating button: null = use default bottom-right position
  const [btnPos, setBtnPos] = useState<{ x: number; y: number } | null>(null)
  const dragState = useRef<{
    dragging: boolean
    startPX: number
    startPY: number
    startBX: number
    startBY: number
    btnW: number
    btnH: number
  } | null>(null)

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
    const stored = localStorage.getItem('jamm_concierge_entry_mode') as 'sidebar' | 'floating' | null
    if (stored === 'sidebar' || stored === 'floating') setConciergeEntryMode(stored)

    const handler = (e: Event) => {
      const mode = (e as CustomEvent<{ mode: 'sidebar' | 'floating' }>).detail.mode
      if (mode === 'sidebar' || mode === 'floating') setConciergeEntryMode(mode)
    }
    window.addEventListener('jamm:concierge-entry-mode-changed', handler)
    return () => window.removeEventListener('jamm:concierge-entry-mode-changed', handler)
  }, [])

  useEffect(() => {
    if (user?.concierge_entry_mode === 'sidebar' || user?.concierge_entry_mode === 'floating') {
      setConciergeEntryMode(user.concierge_entry_mode)
    }
  }, [user])

  // Load persisted button position after mount (SSR-safe: localStorage is browser-only)
  useEffect(() => {
    const stored = localStorage.getItem('jamm_concierge_button_position')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        // Clamp against the current viewport using a conservative button size
        // estimate (real size not yet measurable at load time) so a position
        // saved on a wider viewport never renders the button off screen.
        setBtnPos(clampBtnPos(parsed.x, parsed.y, 150, 36))
      } catch { /* ignore malformed stored value */ }
    }
  }, [])

  function handleConciergeOpen() {
    sessionStorage.setItem('jamm_concierge_open', 'true')
    setConciergeOpen(true)
  }

  function handleConciergeClose() {
    sessionStorage.removeItem('jamm_concierge_open')
    setConciergeOpen(false)
  }

  function clampBtnPos(x: number, y: number, w: number, h: number) {
    const SIDEBAR_WIDTH = 220
    const MARGIN = 12
    return {
      x: Math.max(SIDEBAR_WIDTH + MARGIN, Math.min(window.innerWidth - w - MARGIN, x)),
      y: Math.max(MARGIN, Math.min(window.innerHeight - h - MARGIN, y)),
    }
  }

  function handleBtnPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId)
    const rect = e.currentTarget.getBoundingClientRect()
    dragState.current = {
      dragging: false,
      startPX: e.clientX,
      startPY: e.clientY,
      startBX: rect.left,
      startBY: rect.top,
      btnW: rect.width,
      btnH: rect.height,
    }
  }

  function handleBtnPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const ds = dragState.current
    if (!ds) return
    const dx = e.clientX - ds.startPX
    const dy = e.clientY - ds.startPY
    if (!ds.dragging && Math.abs(dx) < 4 && Math.abs(dy) < 4) return
    ds.dragging = true
    setBtnPos(clampBtnPos(ds.startBX + dx, ds.startBY + dy, ds.btnW, ds.btnH))
  }

  function handleBtnPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    const ds = dragState.current
    if (!ds) return
    dragState.current = null
    if (!ds.dragging) {
      handleConciergeOpen()
      return
    }
    const dx = e.clientX - ds.startPX
    const dy = e.clientY - ds.startPY
    const pos = clampBtnPos(ds.startBX + dx, ds.startBY + dy, ds.btnW, ds.btnH)
    setBtnPos(pos)
    localStorage.setItem('jamm_concierge_button_position', JSON.stringify(pos))
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
        onConciergeOpen={conciergeEntryMode === 'sidebar' ? handleConciergeOpen : undefined}
        locked={isSettingsRoute}
      />
      <main ref={mainRef} className={`flex-1 overflow-y-auto transition-[padding] duration-200 ${conciergeOpen ? 'pr-[400px]' : ''}`}>
        {children}
      </main>
      <ConciergePanel isOpen={conciergeOpen} onClose={handleConciergeClose} />
      {/* Floating entry point -- only rendered in floating mode, hidden when panel is open */}
      {conciergeEntryMode === 'floating' && !conciergeOpen && (
        <div
          className={`fixed z-40 cursor-grab active:cursor-grabbing select-none${btnPos ? '' : ' bottom-6 right-6'}`}
          style={btnPos ? { left: btnPos.x, top: btnPos.y } : undefined}
          onPointerDown={handleBtnPointerDown}
          onPointerMove={handleBtnPointerMove}
          onPointerUp={handleBtnPointerUp}
        >
          <PersistentEntryButton
            onClick={() => {}}
            hasSuggestion={notifications.length > 0}
          />
        </div>
      )}
    </div>
  )
}
