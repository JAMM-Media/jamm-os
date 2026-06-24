// frontend/src/app/staff/page.tsx
'use client'

import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Tabs } from '@/components/ui/Tabs'
import { StaffRoster } from '@/components/staff/StaffRoster'
import { StaffCredentials } from '@/components/staff/StaffCredentials'
import { useAuth } from '@/lib/hooks/useAuth'

const TABS = [
  { key: 'roster', label: 'Roster' },
  { key: 'credentials', label: 'Credentials' },
]

export default function StaffPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<'roster' | 'credentials'>('roster')

  if (user?.role === 'staff') {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[14px] text-[#6B7280]">You do not have permission to view this page.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col p-6 gap-4">
        <h1 className="text-[24px] font-medium text-brand dark:text-[#EDEEF0]">Staff</h1>
        <Tabs
          tabs={TABS}
          active={activeTab}
          onChange={(key) => setActiveTab(key as 'roster' | 'credentials')}
        />
        {activeTab === 'roster' && <StaffRoster />}
        {activeTab === 'credentials' && <StaffCredentials />}
      </div>
    </AppShell>
  )
}
