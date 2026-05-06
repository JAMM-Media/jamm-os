// frontend/src/components/layout/Sidebar.tsx
'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTheme } from 'next-themes'
import {
  LayoutDashboard,
  Users,
  Briefcase,
  CheckSquare,
  FileText,
  CreditCard,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  MessageSquare,
  LogOut,
  CalendarDays,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChannels } from '@/components/firm-chat/useChannels'
import { useAuth } from '@/lib/hooks/useAuth'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/clients', label: 'Clients', icon: Users },
  { href: '/engagements', label: 'Engagements', icon: Briefcase },
  { href: '/tasks', label: 'Tasks', icon: CheckSquare },
  { href: '/calendar', label: 'Calendar', icon: CalendarDays },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/billing', label: 'Billing', icon: CreditCard },
  { href: '/firm-chat', label: 'Firm Chat', icon: MessageSquare },
]

const settingsItem = { href: '/settings', label: 'Settings', icon: Settings }

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const { totalUnread } = useChannels()
  const { logout } = useAuth()

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-brand dark:bg-brand-dark transition-all duration-200 ease-in-out flex-shrink-0',
        collapsed ? 'w-12' : 'w-[220px]'
      )}
    >
      {/* Logo / wordmark + collapse toggle */}
      <div className="flex items-center h-14 px-3 border-b border-white/10 flex-shrink-0">
        {!collapsed && (
          <span className="text-white font-medium text-sm tracking-wide truncate">
            JAMM <span style={{ color: '#B07D3A' }}>PX</span>
          </span>
        )}
        <button
          onClick={onToggle}
          className={cn(
            'ml-auto p-1 rounded text-white/60 hover:text-white hover:bg-white/10 transition-colors',
            collapsed && 'mx-auto'
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Main nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        <ul className="space-y-0.5 px-1.5">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href)
            const Icon = item.icon
            const isFirmChat = item.href === '/firm-chat'
            const showBadge = isFirmChat && totalUnread > 0

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-2 py-2 rounded text-[13px] transition-colors',
                    isActive
                      ? 'bg-white/15 text-white'
                      : 'text-white/60 hover:text-white hover:bg-white/10',
                    collapsed && 'justify-center px-2'
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  {/* Icon — wrap in relative container for collapsed badge */}
                  <div className="relative flex-shrink-0">
                    <Icon className="h-4 w-4" />
                    {showBadge && collapsed && (
                      <span className="absolute -top-1 -right-1 flex items-center justify-center bg-brand dark:bg-brand-btn text-white text-[11px] font-medium w-[18px] h-[18px] rounded-full">
                        {totalUnread > 99 ? '99+' : totalUnread}
                      </span>
                    )}
                  </div>
                  {/* Label + expanded badge */}
                  {!collapsed && (
                    <>
                      <span className="truncate flex-1">{item.label}</span>
                      {showBadge && (
                        <span className="flex items-center justify-center bg-brand dark:bg-brand-btn text-white text-[11px] font-medium h-[18px] min-w-[18px] px-1.5 rounded-full flex-shrink-0">
                          {totalUnread > 99 ? '99+' : totalUnread}
                        </span>
                      )}
                    </>
                  )}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Bottom section: theme toggle + settings */}
      <div className="py-3 px-1.5 border-t border-white/10 flex-shrink-0 space-y-0.5">
        {/* Theme toggle */}
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className={cn(
            'w-full flex items-center gap-3 px-2 py-2 rounded text-[13px] text-white/60 hover:text-white hover:bg-white/10 transition-colors',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? (theme === 'dark' ? 'Light mode' : 'Dark mode') : undefined}
        >
          {mounted && (theme === 'dark' ? (
            <Sun className="h-4 w-4 flex-shrink-0" />
          ) : (
            <Moon className="h-4 w-4 flex-shrink-0" />
          ))}
          {!collapsed && mounted && (
            <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
          )}
        </button>

        {/* Settings */}
        <Link
          href={settingsItem.href}
          className={cn(
            'flex items-center gap-3 px-2 py-2 rounded text-[13px] transition-colors',
            pathname.startsWith(settingsItem.href)
              ? 'bg-white/15 text-white'
              : 'text-white/60 hover:text-white hover:bg-white/10',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? settingsItem.label : undefined}
        >
          <Settings className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span className="truncate">{settingsItem.label}</span>}
        </Link>

        {/* Sign out */}
        {collapsed ? (
          <button
            onClick={logout}
            className="w-full flex items-center justify-center h-9 rounded-md text-white/60 hover:text-white hover:bg-white/10 transition-colors"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-2 py-2 rounded-md text-[13px] text-white/60 hover:text-white hover:bg-white/10 transition-colors"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            <span>Sign out</span>
          </button>
        )}
      </div>
    </aside>
  )
}
