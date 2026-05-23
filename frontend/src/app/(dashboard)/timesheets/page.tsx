// frontend/src/app/(dashboard)/timesheets/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { useAuth } from '@/lib/hooks/useAuth'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import DailyTab from './DailyTab'
import WeeklyTab from './WeeklyTab'
import BiweeklyTab from './BiweeklyTab'
import MonthlyTab from './MonthlyTab'
import QuarterlyTab from './QuarterlyTab'
import YearlyTab from './YearlyTab'

type TabKey = 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'yearly'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'daily', label: 'Daily' },
  { key: 'weekly', label: 'Weekly' },
  { key: 'biweekly', label: 'Biweekly' },
  { key: 'monthly', label: 'Monthly' },
  { key: 'quarterly', label: 'Quarterly' },
  { key: 'yearly', label: 'Yearly' },
]

interface StaffUser {
  id: string
  full_name: string
  email: string
}

export default function TimesheetsPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<TabKey>('daily')
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [staffList, setStaffList] = useState<StaffUser[]>([])

  const isManagerOrAbove =
    user?.role === 'firm_owner' || user?.role === 'manager'

  useEffect(() => {
    if (!isManagerOrAbove) return
    api
      .get('/api/v1/users/?limit=100')
      .then((r) => {
        const items: StaffUser[] = (r.data?.items ?? []).filter(
          (u: StaffUser & { role?: string }) =>
            u.role !== 'client_portal_user' && u.role !== 'system_admin'
        )
        setStaffList(items)
      })
      .catch(() => {})
  }, [isManagerOrAbove])

  if (!user) return null

  return (
    <AppShell>
      <div className="flex flex-col p-6 gap-4">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <h1
            className="font-medium text-[#1F3148] dark:text-[#EDEEF0]"
            style={{ fontSize: 20 }}
          >
            Timesheets
          </h1>
          {isManagerOrAbove && (
            <select
              value={selectedUserId ?? ''}
              onChange={(e) =>
                setSelectedUserId(e.target.value === '' ? null : e.target.value)
              }
              className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none"
            >
              <option value="">All Staff</option>
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name || s.email}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Tab bar */}
        <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'px-4 py-2.5 text-[13px] transition-colors relative',
                activeTab === tab.key
                  ? 'text-[#1F3148] dark:text-[#4A7FA5] font-medium'
                  : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal'
              )}
            >
              {tab.label}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#1F3148] dark:bg-[#4A7FA5]" />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'daily' && (
          <DailyTab
            selectedUserId={selectedUserId}
            currentUserId={user.id}
            userRole={user.role}
          />
        )}
        {activeTab === 'weekly' && (
          <WeeklyTab
            selectedUserId={selectedUserId}
            currentUserId={user.id}
            userRole={user.role}
          />
        )}
        {activeTab === 'biweekly' && (
          <BiweeklyTab
            selectedUserId={selectedUserId}
            currentUserId={user.id}
            userRole={user.role}
          />
        )}
        {activeTab === 'monthly' && (
          <MonthlyTab
            selectedUserId={selectedUserId}
            currentUserId={user.id}
            userRole={user.role}
          />
        )}
        {activeTab === 'quarterly' && (
          <QuarterlyTab
            selectedUserId={selectedUserId}
            currentUserId={user.id}
            userRole={user.role}
          />
        )}
        {activeTab === 'yearly' && (
          <YearlyTab
            selectedUserId={selectedUserId}
            currentUserId={user.id}
            userRole={user.role}
          />
        )}
      </div>
    </AppShell>
  )
}
