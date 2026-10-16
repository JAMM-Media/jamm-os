// path: frontend/src/components/calendar/EventDetailsPopoverEditFlow.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'
import { EventDetailsPopover } from './EventDetailsPopover'
import type { CalendarEvent } from '@/lib/api/calendarEvents'
import type { EventUser } from '@/lib/calendarEventPermissions'

// The edit modal mock exposes a Save button that calls onCreated, which the
// shared mock in EventDetailsPopover.test.tsx cannot do.
vi.mock('@/components/calendar/NewEventModal', async () => {
  const { createElement: h } = await import('react')
  return {
    NewEventModal: ({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) => {
      if (!open) return null
      return h('div', { role: 'dialog', 'aria-label': 'edit-modal' },
        h('button', { onClick: onCreated }, 'Save modal'),
        h('button', { onClick: onClose }, 'Close modal')
      )
    },
  }
})

vi.mock('@/lib/api/calendarEvents', () => ({
  calendarEventsApi: {},
  buildEventPatch: () => ({}),
}))

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const TZ = 'America/New_York'
const SELF = 'user-self'
const staffUser: EventUser = { id: SELF, role: 'staff' }

function makeEvent(): CalendarEvent {
  return {
    id: 'ev-1',
    title: 'Team standup',
    startAt: '2026-10-14T14:00:00Z',
    endAt: '2026-10-14T15:00:00Z',
    eventTimezone: TZ,
    categoryId: null,
    categoryName: null,
    categoryColor: null,
    clientId: null,
    clientName: null,
    ownerUserId: SELF,
    ownerName: 'Alice',
    createdBy: SELF,
    createdAt: '2026-10-01T00:00:00Z',
    updatedAt: '2026-10-01T00:00:00Z',
    deletedAt: null,
    staffNotes: null,
    completedAt: null,
    isDone: false,
    deleteRequestedAt: null,
    deleteRequestedBy: null,
    deleteRequestReason: null,
  }
}

describe('edit flow: successful save', () => {
  it('a successful save in the edit modal calls onMutated and closes the popover', async () => {
    const onClose = vi.fn()
    const onMutated = vi.fn()
    const user = userEvent.setup()
    render(
      <EventDetailsPopover
        event={makeEvent()}
        pos={{ x: 100, y: 100 }}
        onClose={onClose}
        onMutated={onMutated}
        timeZone={TZ}
        user={staffUser}
      />
    )
    await user.click(screen.getByRole('button', { name: /edit/i }))
    await user.click(screen.getByRole('button', { name: /save modal/i }))
    expect(onMutated).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
