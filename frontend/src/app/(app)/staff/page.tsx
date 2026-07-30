// frontend/src/app/staff/page.tsx
'use client'

import { useState } from 'react'
import { Tabs } from '@/components/ui/Tabs'
import { StaffRoster } from '@/components/staff/StaffRoster'
import { StaffCredentials } from '@/components/staff/StaffCredentials'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import { ContextualBanner } from '@/components/concierge-inline/ContextualBanner'
import { emitConciergeAction } from '@/lib/events/conciergeEvents'
import api from '@/lib/api'

const TABS = [
  { key: 'roster', label: 'Roster' },
  { key: 'credentials', label: 'Credentials' },
]

export default function StaffPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState<'roster' | 'credentials'>('roster')
  const isManagerOrAbove = user?.role === 'firm_owner' || user?.role === 'manager'
  const { data: capacityData } = useFetch(
    () => isManagerOrAbove
      ? api.get('/users/capacity').then((r) => r.data as { overloaded_count: number })
      : Promise.resolve(null),
    [isManagerOrAbove]
  )

  if (user?.role === 'staff') {
    return (
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[14px] text-[#6B7280]">You do not have permission to view this page.</p>
        </div>
    )
  }

  const overloadedCount = capacityData?.overloaded_count ?? 0

  return (
      <div className="flex flex-col p-6 gap-4">
        <h1 className="text-[24px] font-medium text-brand dark:text-[#EDEEF0]">Staff</h1>
        {overloadedCount > 0 && user?.concierge_suggestions_enabled !== false && (
          <ContextualBanner
            tone="amber"
            count={overloadedCount}
            message={`staff member${overloadedCount === 1 ? '' : 's'} at or above full capacity this week.`}
            actionLabel="Ask Concierge"
            onAction={() => {
              emitConciergeAction({ type: 'open-panel' })
              emitConciergeAction({ type: 'prefill-panel-input', prefillMessage: 'Which staff members are overloaded this week?' })
            }}
          />
        )}
        <Tabs
          tabs={TABS}
          active={activeTab}
          onChange={(key) => setActiveTab(key as 'roster' | 'credentials')}
        />
        {activeTab === 'roster' && <StaffRoster />}
        {activeTab === 'credentials' && <StaffCredentials />}
      </div>
  )
}
