// frontend/src/app/(app)/dev/concierge-kit/page.tsx
'use client'

import { useState } from 'react'
import { SuggestionCard } from '@/components/concierge-inline/SuggestionCard'
import { ContextualBanner } from '@/components/concierge-inline/ContextualBanner'
import { GhostTextField } from '@/components/concierge-inline/GhostTextField'
import { PersistentEntryButton } from '@/components/concierge-inline/PersistentEntryButton'
import { ContextLoadedChatPreview } from '@/components/concierge-inline/ContextLoadedChatPreview'

const mockNotification = {
  id: 'mock-notif-1',
  trigger_type: 'client_comm_gap',
  message: "You haven't reached out to 3 clients with active work in over 30 days: Acme Corp, Patricia Nguyen, and Robert & Carol Tanner.",
  created_at: new Date().toISOString(),
  metadata: {
    draft: "Hi, just checking in on the status of your return. Let me know if you have any questions or if there's anything I can help move forward.",
    client_id: 'mock-client-1',
  },
}

const mockNotificationNoDraft = {
  id: 'mock-notif-2',
  trigger_type: 'stalled_work',
  message: "It looks like 2 of your engagements haven't moved in over two weeks: Bob Corp (Bookkeeping), Jane Doe (Tax Return). Want to review what's holding them up?",
  created_at: new Date().toISOString(),
  metadata: {},
}

export default function ConciergeKitPage() {
  const [showCard1, setShowCard1] = useState(true)
  const [showCard2, setShowCard2] = useState(true)
  const [ghostValue, setGhostValue] = useState('Check in with')

  return (
    <div className="p-8 flex flex-col gap-10 max-w-2xl">
      <div>
        <h1 className="text-2xl font-display font-medium text-brand dark:text-foreground mb-1">
          Concierge Inline Kit
        </h1>
        <p className="text-[13px] text-muted-foreground">
          Isolated component preview. Not wired into any real page.
        </p>
      </div>

      {/* SuggestionCard -- with action */}
      <section className="flex flex-col gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          1. SuggestionCard
        </h2>
        {showCard1 ? (
          <SuggestionCard
            notification={mockNotification}
            actionLabel="Review clients"
            onAction={() => alert('onAction fired')}
            onDismiss={() => setShowCard1(false)}
          />
        ) : (
          <button
            onClick={() => setShowCard1(true)}
            className="text-[12px] text-brand-light hover:underline self-start"
          >
            Restore card
          </button>
        )}
        {showCard2 ? (
          <SuggestionCard
            notification={mockNotificationNoDraft}
            onDismiss={() => setShowCard2(false)}
          />
        ) : (
          <button
            onClick={() => setShowCard2(true)}
            className="text-[12px] text-brand-light hover:underline self-start"
          >
            Restore card (no action)
          </button>
        )}
      </section>

      {/* ContextualBanner */}
      <section className="flex flex-col gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          2. ContextualBanner
        </h2>
        <ContextualBanner
          tone="green"
          count={4}
          message="bookkeeping entries are ready to post to QuickBooks."
          actionLabel="Post all"
          onAction={() => alert('Post all clicked')}
        />
        <ContextualBanner
          tone="amber"
          count={2}
          message="client invoices are past due by more than 30 days."
          actionLabel="Review"
          onAction={() => alert('Review clicked')}
        />
      </section>

      {/* GhostTextField */}
      <section className="flex flex-col gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          3. GhostTextField
        </h2>
        <p className="text-[12px] text-muted-foreground">
          Type to see ghost completion appear after cursor.
        </p>
        <GhostTextField
          value={ghostValue}
          onChange={setGhostValue}
          suggestedCompletion=" Acme Corp about their Q2 bookkeeping review."
          placeholder="Start typing a client message..."
          rows={3}
        />
      </section>

      {/* PersistentEntryButton */}
      <section className="flex flex-col gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          4. PersistentEntryButton
        </h2>
        <div className="flex items-center gap-3">
          <PersistentEntryButton onClick={() => alert('Open Concierge')} />
          <PersistentEntryButton onClick={() => alert('Draft message')} label="Draft message" />
        </div>
      </section>

      {/* ContextLoadedChatPreview */}
      <section className="flex flex-col gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          5. ContextLoadedChatPreview
        </h2>
        <p className="text-[12px] text-muted-foreground">
          Intended to appear at the top of the panel when opened from an inline component.
        </p>
        <div className="rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          <ContextLoadedChatPreview openedFromLabel="Dashboard / 3 clients not contacted" />
          <div className="px-4 py-6 text-[12px] text-muted-foreground text-center">
            (Panel body would appear here)
          </div>
        </div>
      </section>
    </div>
  )
}
