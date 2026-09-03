// frontend/src/components/portal/PortalShell.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  CheckSquare,
  FolderOpen,
  Receipt,
  BarChart3,
  BookOpen,
  MessageSquare,
  Settings,
  Bell,
  ChevronDown,
  LogOut,
} from 'lucide-react'
import { usePortalUnreadMessages } from './usePortalUnreadMessages'
import { PortalNotificationBell } from './PortalNotificationBell'

interface PortalShellProps {
  firmName: string
  logoUrl?: string
  brandColor?: string
  // pageColor is accepted to avoid breaking callers but is no longer used as the
  // outer shell background. The content area uses a fixed light neutral (CONTENT_BG).
  pageColor?: string
  // tabBarColor is accepted to avoid breaking callers. The horizontal tab bar is
  // replaced by a sidebar; sidebar background uses brandColor.
  tabBarColor?: string
  accentColor?: string
  avatarColor?: string
  subtitleColor?: string
  // portalMode is accepted but not applied to the shell layout. The sidebar is always
  // dark navy (driven by brandColor). Individual page content may still use this prop
  // for their own internal styling.
  portalMode?: 'light' | 'dark'
  clientName: string
  activeTab: string
  onTabChange: (tab: string) => void
  children: React.ReactNode
}

// Light neutral for the main content area. Replaces the per-firm pageColor in the
// shell layout; content pages will get their own light-theme pass separately.
const CONTENT_BG = '#F7F8FA'

const NAV_ITEMS = [
  { key: 'todo',            label: 'To-do',          Icon: CheckSquare },
  { key: 'documents',      label: 'Documents',       Icon: FolderOpen },
  { key: 'invoices',       label: 'Invoices',        Icon: Receipt },
  { key: 'billing-detail', label: 'Billing Detail',  Icon: BarChart3 },
  { key: 'organizer',      label: 'Tax Organizer',   Icon: BookOpen },
  { key: 'messages',       label: 'Messages',        Icon: MessageSquare },
  { key: 'notifications',  label: 'Notifications',   Icon: Bell },
]

export function PortalShell({
  firmName,
  logoUrl,
  brandColor = '#1A2535',
  pageColor: _pageColor,
  tabBarColor: _tabBarColor,
  accentColor = '#4A7FA5',
  avatarColor = '#3A6A94',
  subtitleColor = '#7DA3C4',
  portalMode: _portalMode,
  clientName,
  activeTab,
  onTabChange,
  children,
}: PortalShellProps) {
  const router = useRouter()
  const { unreadCount, markAsRead } = usePortalUnreadMessages()
  const [logoError, setLogoError] = useState(false)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const avatarRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (avatarRef.current && !avatarRef.current.contains(e.target as Node)) {
        setAvatarOpen(false)
      }
    }
    if (avatarOpen) {
      document.addEventListener('mousedown', handleOutsideClick)
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [avatarOpen])

  const sidebarTextActive = '#FFFFFF'
  const sidebarTextMuted = 'rgba(255, 255, 255, 0.75)'
  const sidebarActiveBg = 'rgba(255, 255, 255, 0.10)'

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <div
        className="w-56 flex flex-col flex-shrink-0 h-screen"
        style={{ backgroundColor: brandColor }}
      >
        {/* Firm identity */}
        <div className="px-4 pt-5 pb-4">
          {logoUrl && !logoError ? (
            <img
              src={logoUrl}
              alt={firmName}
              className="h-7 max-w-[140px] object-contain mb-1"
              onError={() => setLogoError(true)}
            />
          ) : (
            <p className="text-[13px] font-semibold text-white leading-tight mb-0.5">{firmName}</p>
          )}
          <p
            className="text-[9px] font-semibold tracking-widest uppercase"
            style={{ color: subtitleColor }}
          >
            Client Portal
          </p>
        </div>

        <div className="mx-3 border-t mb-2" style={{ borderColor: 'rgba(255,255,255,0.10)' }} />

        {/* Nav items */}
        <nav className="flex-1 px-2 flex flex-col gap-0.5">
          {NAV_ITEMS.map(({ key, label, Icon }) => {
            const isActive = activeTab === key
            const hasBadge = key === 'messages' && unreadCount > 0
            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  onTabChange(key)
                  if (key === 'messages') markAsRead()
                }}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors"
                style={{
                  backgroundColor: isActive ? sidebarActiveBg : 'transparent',
                  color: isActive ? sidebarTextActive : sidebarTextMuted,
                  borderLeft: isActive ? `3px solid ${accentColor}` : '3px solid transparent',
                }}
              >
                <Icon size={16} className="flex-shrink-0" />
                <span className="text-[14px] font-medium flex-1 truncate">{label}</span>
                {hasBadge && (
                  <span
                    className="text-[10px] font-semibold text-white px-1.5 py-0.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: accentColor }}
                  >
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Main content column */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* Floating bell + avatar: no bar, no background, no border -- sits on CONTENT_BG */}
        <div className="absolute top-4 right-5 z-10 flex items-center gap-3 pointer-events-auto">
          <PortalNotificationBell />

          {/* Avatar dropdown -- Settings + Logout */}
          <div className="relative" ref={avatarRef}>
            <button
              type="button"
              onClick={() => setAvatarOpen((v) => !v)}
              className="flex items-center gap-1.5 rounded-lg px-1 py-1 hover:bg-black/5 transition-colors"
              aria-label="Account menu"
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center"
                style={{ backgroundColor: avatarColor }}
              >
                <span className="text-[10px] font-semibold text-white">
                  {clientName?.charAt(0).toUpperCase() ?? '?'}
                </span>
              </div>
              <ChevronDown size={13} style={{ color: '#9CA3AF' }} className="flex-shrink-0" />
            </button>
            {avatarOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-52 rounded-xl bg-white border border-gray-100 shadow-lg overflow-hidden z-20">
                {/* "Signed in as" header -- non-clickable identity row */}
                <div className="px-4 py-3">
                  <p className="text-[11px]" style={{ color: '#9CA3AF' }}>Signed in as</p>
                  <p className="text-[12px] font-medium truncate mt-0.5" style={{ color: '#374151' }}>
                    {clientName}
                  </p>
                </div>
                <div className="h-px bg-gray-100" />
                <button
                  type="button"
                  onClick={() => { setAvatarOpen(false); router.push('/portal/settings') }}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-[13px] hover:bg-gray-50 transition-colors"
                  style={{ color: '#374151' }}
                >
                  <Settings size={14} style={{ color: '#6B7280' }} />
                  Settings
                </button>
                <div className="h-px bg-gray-100 mx-3" />
                <button
                  type="button"
                  onClick={() => {
                    localStorage.removeItem('portal_access_token')
                    router.push('/portal/login')
                  }}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-left text-[13px] hover:bg-gray-50 transition-colors"
                  style={{ color: '#DC2626' }}
                >
                  <LogOut size={14} style={{ color: '#DC2626' }} />
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Scrollable content area: starts at top of column, no bar above it */}
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: CONTENT_BG }}>
          {children}
        </main>
      </div>
    </div>
  )
}
