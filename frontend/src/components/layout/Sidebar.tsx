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
  Bell,
  Clock,
  LayoutTemplate,
  BotMessageSquare,
  Plug,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { useChannels } from '@/components/firm-chat/useChannels'
import { useAuth } from '@/lib/hooks/useAuth'
import api from '@/lib/api'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/clients', label: 'Clients', icon: Users },
  { href: '/engagements', label: 'Engagements', icon: Briefcase },
  { href: '/templates', label: 'Templates', icon: LayoutTemplate },
  { href: '/tasks', label: 'Tasks', icon: CheckSquare },
  { href: '/timesheets', label: 'Timesheets', icon: Clock },
  { href: '/calendar', label: 'Calendar', icon: CalendarDays },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/billing', label: 'Billing', icon: CreditCard },
  { href: '/firm-chat', label: 'Firm Chat', icon: MessageSquare },
  { href: '/notifications', label: 'Notifications', icon: Bell },
]

const settingsItem = { href: '/settings', label: 'Settings', icon: Settings }
const myIntegrationsItem = { href: '/settings/my-integrations', label: 'My Integrations', icon: Plug }

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  onConciergeOpen: () => void
}

export function Sidebar({ collapsed, onToggle, onConciergeOpen }: SidebarProps) {
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const { totalUnread } = useChannels()
  const { logout, user } = useAuth()

  const { data: notifData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => api.get('/api/v1/notifications/unread-count').then((r) => r.data),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  })
  const notifUnread: number = notifData?.count ?? 0

  const visibleNavItems = navItems.filter((item) => {
    if (item.href === '/dashboard' && user?.role === 'staff') return false
    return true
  })

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
          {visibleNavItems.map((item) => {
            const isActive = pathname.startsWith(item.href)
            const Icon = item.icon
            const isFirmChat = item.href === '/firm-chat'
            const isNotifications = item.href === '/notifications'
            const showNotifBadge = isNotifications && notifUnread > 0
            const badgeCount = isNotifications ? notifUnread : totalUnread
            const showBadge = (isFirmChat && totalUnread > 0) || showNotifBadge

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
                        {badgeCount > 99 ? '99+' : badgeCount}
                      </span>
                    )}
                  </div>
                  {/* Label + expanded badge */}
                  {!collapsed && (
                    <>
                      <span className="truncate flex-1">{item.label}</span>
                      {showBadge && (
                        <span className="flex items-center justify-center bg-brand dark:bg-brand-btn text-white text-[11px] font-medium h-[18px] min-w-[18px] px-1.5 rounded-full flex-shrink-0">
                          {badgeCount > 99 ? '99+' : badgeCount}
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

        {/* Concierge */}
        <button
          onClick={onConciergeOpen}
          className={cn(
            'w-full flex items-center gap-3 px-2 py-2 rounded text-[13px] text-white/60 hover:text-white hover:bg-white/10 transition-colors',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'JAMM Concierge' : undefined}
        >
          <BotMessageSquare className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span className="truncate">JAMM Concierge</span>}
        </button>

        {/* My Integrations */}
        <Link
          href={myIntegrationsItem.href}
          className={cn(
            'flex items-center gap-3 px-2 py-2 rounded text-[13px] transition-colors',
            pathname === myIntegrationsItem.href
              ? 'bg-white/15 text-white'
              : 'text-white/60 hover:text-white hover:bg-white/10',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? myIntegrationsItem.label : undefined}
        >
          <Plug className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span className="truncate">{myIntegrationsItem.label}</span>}
        </Link>

        {/* Settings */}
        <Link
          href={settingsItem.href}
          className={cn(
            'flex items-center gap-3 px-2 py-2 rounded text-[13px] transition-colors',
            pathname.startsWith(settingsItem.href) && pathname !== myIntegrationsItem.href
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
