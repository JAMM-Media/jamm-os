// frontend/src/components/portal/PortalShell.tsx
'use client'

import { useState } from 'react'
import { usePortalUnreadMessages } from './usePortalUnreadMessages'

interface PortalShellProps {
  firmName: string
  logoUrl?: string
  brandColor?: string
  pageColor?: string
  tabBarColor?: string
  accentColor?: string
  avatarColor?: string
  subtitleColor?: string
  portalMode?: 'light' | 'dark'
  clientName: string
  activeTab: string
  onTabChange: (tab: string) => void
  children: React.ReactNode
}

export function PortalShell({
  firmName,
  logoUrl,
  brandColor = '#1A2535',
  pageColor = '#2D2D2D',
  tabBarColor = '#252525',
  accentColor = '#4A7FA5',
  avatarColor = '#3A6A94',
  subtitleColor = '#7DA3C4',
  portalMode = 'dark',
  clientName,
  activeTab,
  onTabChange,
  children,
}: PortalShellProps) {
  const { unreadCount, markAsRead } = usePortalUnreadMessages()
  const [logoError, setLogoError] = useState(false)

  const isLight = portalMode === 'light'
  const primaryText = isLight ? '#1F3148' : '#EDEEF0'
  const mutedText = isLight ? '#6B7280' : '#9CA3AF'
  const tabBorder = isLight ? '#C8CDD6' : '#383838'

  const tabs = [
    { key: 'todo', label: 'To-do' },
    { key: 'documents', label: 'Documents' },
    { key: 'invoices', label: 'Invoices' },
    { key: 'messages', label: 'Messages', badge: unreadCount > 0 ? unreadCount : null },
  ]

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: pageColor }}>
      {/* Top bar */}
      <div
        className="flex items-center justify-between px-5 h-12 flex-shrink-0"
        style={{ backgroundColor: brandColor }}
      >
        <div className="flex items-center gap-2">
          {logoUrl && !logoError ? (
            <img
              src={logoUrl}
              alt={firmName}
              className="h-6 max-w-[120px] object-contain"
              onError={() => setLogoError(true)}
            />
          ) : (
            <span className="text-[12px] font-medium text-white">{firmName}</span>
          )}
          <span className="text-[10px]" style={{ color: subtitleColor }}>Client Portal</span>
        </div>
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center cursor-pointer"
          style={{ backgroundColor: avatarColor }}
        >
          <span className="text-[11px] font-medium text-white">
            {clientName?.charAt(0).toUpperCase() ?? '?'}
          </span>
        </div>
      </div>

      {/* Tab bar */}
      <div
        className="flex items-center px-4 flex-shrink-0 border-b"
        style={{ backgroundColor: tabBarColor, borderColor: tabBorder }}
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => {
                onTabChange(tab.key)
                if (tab.key === 'messages') markAsRead()
              }}
              className="relative flex items-center gap-1.5 px-3 py-2.5 text-[12px] font-medium transition-colors"
              style={{
                color: isActive ? primaryText : mutedText,
                borderBottom: isActive ? `2px solid ${accentColor}` : '2px solid transparent',
              }}
            >
              {tab.label}
              {tab.badge && (
                <span
                  className="text-[10px] font-medium text-white px-1.5 py-0.5 rounded-full"
                  style={{ backgroundColor: accentColor }}
                >
                  {tab.badge > 99 ? '99+' : tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
