// frontend/src/components/layout/Sidebar.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTheme } from 'next-themes'
import {
  LayoutDashboard,
  Users,
  Briefcase,
  CheckSquare,
  CreditCard,
  Settings,
  ChevronLeft,
  Sun,
  Moon,
  MessageSquare,
  LogOut,
  CalendarDays,
  Bell,
  Clock,
  LayoutTemplate,
  BotMessageSquare,
  Mail,
  UserCog,
  Archive,
  Sprout,
  TrendingUp,
  Library,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'
import { useChannels } from '@/components/firm-chat/useChannels'
import { useAuth } from '@/lib/hooks/useAuth'
import api from '@/lib/api'

interface NavItem {
  href: string
  label: string
  icon: React.ElementType
}

interface NavSection {
  label: string | null
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    label: null,
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    ],
  },
  {
    label: 'Client Work',
    items: [
      { href: '/clients', label: 'Clients', icon: Users },
      { href: '/leads', label: 'Pipeline', icon: TrendingUp },
      { href: '/engagements', label: 'Engagements', icon: Briefcase },
      { href: '/tasks', label: 'Tasks', icon: CheckSquare },
      { href: '/templates', label: 'Templates', icon: LayoutTemplate },
    ],
  },
  {
    label: 'Time & Billing',
    items: [
      { href: '/timesheets', label: 'Timesheets', icon: Clock },
      { href: '/billing', label: 'Billing', icon: CreditCard },
    ],
  },
  {
    label: 'Firm',
    items: [
      { href: '/staff', label: 'Staff', icon: UserCog },
      { href: '/firm-library', label: 'Firm Library', icon: Library },
      { href: '/calendar', label: 'Calendar', icon: CalendarDays },
      { href: '/archive', label: 'Archive', icon: Archive },
    ],
  },
  {
    label: 'Communication',
    items: [
      { href: '/inbox', label: 'Inbox', icon: Mail },
      { href: '/firm-chat', label: 'Firm Chat', icon: MessageSquare },
      { href: '/notifications', label: 'Notifications', icon: Bell },
      { href: '/peer-network', label: 'Peer Network', icon: Sprout },
    ],
  },
]

const settingsItem = { href: '/settings', label: 'Settings', icon: Settings }

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  onConciergeOpen?: () => void
  locked?: boolean
}

export function Sidebar({ collapsed, onToggle, onConciergeOpen, locked }: SidebarProps) {
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  const navRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const nav = navRef.current
    if (!nav) return

    const saved = sessionStorage.getItem('jamm_sidebar_scroll')
    if (saved) nav.scrollTop = parseInt(saved, 10)

    function handleScroll() {
      sessionStorage.setItem('jamm_sidebar_scroll', String(nav!.scrollTop))
    }
    nav.addEventListener('scroll', handleScroll)
    return () => nav.removeEventListener('scroll', handleScroll)
  }, [])
  const { totalUnread } = useChannels()
  const { logout, user } = useAuth()

  const { data: notifData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => api.get('/api/v1/notifications/unread-count').then((r) => r.data),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  })
  const notifUnread: number = notifData?.count ?? 0

  const { data: firmData } = useQuery({
    queryKey: ['firm-settings-sidebar'],
    queryFn: () => api.get('/users/firm').then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

  const { data: myIntegrations } = useQuery({
    queryKey: ['my-integrations-sidebar'],
    queryFn: () => api.get('/api/v1/integrations/staff/me').then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

  const emailSyncEnabled = (firmData as { settings?: { email_sync_enabled?: boolean } } | undefined)?.settings?.email_sync_enabled !== false

  const myEmailDisabledByFirm = Array.isArray(myIntegrations) && myIntegrations.some(
    (i: { provider: string; firm_disabled: boolean }) =>
      (i.provider === 'gmail' || i.provider === 'outlook') && i.firm_disabled
  )

  function isItemVisible(item: NavItem): boolean {
    if (item.href === '/dashboard' && user?.role === 'staff') return false
    if (item.href === '/staff' && user?.role === 'staff') return false
    if (item.href === '/inbox') return emailSyncEnabled && !myEmailDisabledByFirm
    return true
  }

  return (
    <aside
      className={cn(
        'flex flex-col h-screen bg-brand dark:bg-brand-dark transition-all duration-200 ease-in-out flex-shrink-0',
        collapsed ? 'w-12' : 'w-[220px]'
      )}
    >
      {/* Logo / wordmark + collapse toggle */}
      {locked ? (
        <div className="h-14 border-b border-white/10 flex-shrink-0" />
      ) : (
        <div className="flex items-center h-14 px-3 border-b border-white/10 flex-shrink-0">
          {collapsed ? (
            /* Collapsed: mark doubles as the expand button */
            <button
              onClick={onToggle}
              className="mx-auto flex items-center justify-center p-1 rounded hover:bg-white/10 transition-colors"
              aria-label="Expand sidebar"
              title="Expand sidebar"
            >
              <img
                src="/jamm-logo-mark-light.svg"
                alt=""
                style={{ height: 20, width: 20, objectFit: 'contain' }}
              />
            </button>
          ) : (
            <>
              <div className="flex items-center gap-2 min-w-0 overflow-hidden">
                <img
                  src="/jamm-logo-mark-light.svg"
                  alt=""
                  className="flex-shrink-0"
                  style={{ height: 20 }}
                />
                <span
                  className="text-white text-[15px] tracking-wide truncate"
                  style={{ fontFamily: 'var(--font-playfair)' }}
                >
                  JAMM <span style={{ color: '#B07D3A' }}>PX</span>
                </span>
              </div>
              <button
                onClick={onToggle}
                className="ml-auto p-1 rounded text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                aria-label="Collapse sidebar"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      )}

      {/* Main nav -- overflow-y-auto with thin scrollbar so items at the bottom are
          reachable on short screens. survey-scroll is defined in globals.css and
          applies scrollbar-width:thin plus a matching scrollbar-color for the navy
          background. The bottom cluster sits outside this element and never scrolls. */}
      <nav ref={navRef} className="flex-1 py-3 overflow-y-auto survey-scroll">
        {navSections.map((section) => {
          const visibleItems = section.items.filter(isItemVisible)
          if (visibleItems.length === 0) return null

          return (
            <div key={section.label ?? '__root__'}>
              {/* Expanded: section label header. Collapsed: thin divider between sections.
                  The null-label Dashboard section gets neither. */}
              {section.label !== null && (
                collapsed ? (
                  <div className="mx-1.5 mt-3 mb-1 border-t border-white/10" />
                ) : (
                  <p className="px-3.5 pt-4 pb-1 text-[11px] font-medium text-white/40 uppercase tracking-[0.05em]">
                    {section.label}
                  </p>
                )
              )}
              <ul className="space-y-0.5 px-1.5">
                {visibleItems.map((item) => {
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
                        scroll={false}
                        className={cn(
                          'flex items-center gap-3 px-2 py-2 rounded text-[13px] transition-colors',
                          isActive
                            ? 'bg-white/15 text-white'
                            : 'text-white/60 hover:text-white hover:bg-white/10',
                          /* Gold left-edge indicator on the active item in expanded state.
                             In collapsed state the icon itself turns gold instead (see Icon below),
                             since a 3px bar is too narrow to read at 48px width. */
                          isActive && !collapsed && 'border-l-[3px] border-[#B07D3A]',
                          collapsed && 'justify-center px-2'
                        )}
                        title={collapsed ? item.label : undefined}
                      >
                        {/* Icon: wrap in relative container for collapsed badge.
                            Active + collapsed: icon turns gold to signal "you are here" at 48px width. */}
                        <div className="relative flex-shrink-0">
                          <Icon
                            className={cn(
                              'h-4 w-4',
                              isActive && collapsed && 'text-[#B07D3A]'
                            )}
                          />
                          {showBadge && collapsed && (
                            <span className="absolute -top-1 -right-1 flex items-center justify-center bg-[#B07D3A] dark:bg-brand-btn text-white text-[11px] font-medium w-[18px] h-[18px] rounded-full">
                              {badgeCount > 99 ? '99+' : badgeCount}
                            </span>
                          )}
                        </div>
                        {/* Label + expanded badge */}
                        {!collapsed && (
                          <>
                            <span className="truncate flex-1">{item.label}</span>
                            {showBadge && (
                              <span className="flex items-center justify-center bg-[#B07D3A] dark:bg-brand-btn text-white text-[11px] font-medium h-[18px] min-w-[18px] px-1.5 rounded-full flex-shrink-0">
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
            </div>
          )
        })}
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


        {onConciergeOpen && (
          <>
            {/* Concierge */}
            <button
              onClick={onConciergeOpen}
              className={cn(
                'w-full flex items-center gap-3 px-2 py-2 rounded text-[13px] text-white/60 hover:text-white hover:bg-white/10 transition-colors',
                collapsed && 'justify-center px-2'
              )}
              title={collapsed ? 'JAMM Concierge' : undefined}
            >
              <BotMessageSquare className='h-4 w-4 flex-shrink-0' />
              {!collapsed && <span className='truncate'>JAMM Concierge</span>}
            </button>
          </>
        )}

        {/* Settings */}
        <Link
          href={settingsItem.href}
          scroll={false}
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
