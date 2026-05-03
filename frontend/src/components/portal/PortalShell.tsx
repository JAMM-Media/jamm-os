// frontend/src/components/portal/PortalShell.tsx
'use client'

import { cn } from '@/lib/utils'
import { usePortalUnreadMessages } from './usePortalUnreadMessages'

interface PortalShellProps {
  firmName: string
  clientName: string
  activeTab: string
  onTabChange: (tab: string) => void
  children: React.ReactNode
}

const TABS = [
  { key: 'todo', label: 'To-do' },
  { key: 'documents', label: 'Documents' },
  { key: 'invoices', label: 'Invoices' },
  { key: 'messages', label: 'Messages' },
]

export function PortalShell({
  firmName,
  clientName,
  activeTab,
  onTabChange,
  children,
}: PortalShellProps) {
  const { unreadCount, markAsRead } = usePortalUnreadMessages()

  function handleTabChange(key: string) {
    if (key === 'messages') markAsRead()
    onTabChange(key)
  }

  return (
    <div className="min-h-screen bg-[#2D2D2D] flex flex-col">
      {/* Top bar — always #1F3148 */}
      <div className="flex items-center justify-between px-5 h-12 bg-[#1F3148] flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-white">
            {firmName}
          </span>
          <span className="text-[10px] text-[#7DA3C4]">
            Client Portal
          </span>
        </div>
        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-[#3A6A94] flex items-center justify-center">
          <span className="text-[11px] font-medium text-white">
            {clientName.split(' ').map((n) => n[0]).join('').slice(0, 2)}
          </span>
        </div>
      </div>

      {/* Tab row */}
      <div className="flex items-end gap-0 px-5 bg-[#252525] border-b border-[#383838] flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={cn(
              'px-4 py-2.5 text-[13px] relative transition-colors flex items-center gap-1.5',
              activeTab === tab.key
                ? 'text-[#EDEEF0] font-medium'
                : 'text-[#9CA3AF] hover:text-[#EDEEF0] font-normal'
            )}
          >
            {tab.label}
            {tab.key === 'messages' && unreadCount > 0 && (
              <span
                className="inline-flex items-center justify-center bg-brand dark:bg-brand-btn text-[#EDEEF0]"
                style={{
                  height: 18,
                  minWidth: 18,
                  padding: '0 6px',
                  borderRadius: 9999,
                  fontSize: 11,
                  fontWeight: 500,
                  lineHeight: 1,
                }}
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
            {activeTab === tab.key && (
              <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#4A7FA5]" />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  )
}
