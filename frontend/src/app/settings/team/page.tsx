// frontend/src/app/settings/team/page.tsx
'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { onConciergeAction } from '@/lib/events/conciergeEvents'

export default function SettingsTeamPage() {
  const router = useRouter()
  const inviteRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'invite-staff') {
        inviteRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }, [])

  return (
    <AppShell>
      <div className="p-6 flex flex-col gap-4 max-w-2xl">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/settings')}
            className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            Settings
          </button>
          <span className="text-[#9CA3AF]">/</span>
          <span className="text-[12px] text-brand dark:text-[#EDEEF0]">Team</span>
        </div>

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Team</h1>

        <div
          ref={inviteRef}
          className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border dark:border-dark-border p-5"
          style={{ borderWidth: '0.5px' }}
        >
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-1">
            Invite Team Member
          </p>
          <p className="text-[12px] text-[#6B7280] mb-1">
            Add a staff member to your firm. Use the full Settings page to manage roles
            and view existing team members.
          </p>
          <button
            onClick={() => router.push('/settings?tab=team')}
            className="text-[12px] text-brand dark:text-[#4A7FA5] underline"
          >
            Open full team settings
          </button>
        </div>
      </div>
    </AppShell>
  )
}
