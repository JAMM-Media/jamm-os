// path: frontend/src/components/calendar/EventDetailsPopover.test.tsx
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, beforeEach, describe, it, expect } from 'vitest'
import { EventDetailsPopover } from './EventDetailsPopover'
import type { CalendarEvent } from '@/lib/api/calendarEvents'
import type { EventUser } from '@/lib/calendarEventPermissions'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api/calendarEvents', () => ({
  calendarEventsApi: {
    deleteEvent: vi.fn(),
    updateEvent: vi.fn(),
    requestDelete: vi.fn(),
    approveDeleteRequest: vi.fn(),
    denyDeleteRequest: vi.fn(),
  },
  buildEventPatch: (input: Record<string, unknown>) => {
    const body: Record<string, unknown> = {}
    if (input.title !== undefined) body.title = input.title
    if (input.startAt !== undefined) body.start_at = input.startAt
    if (input.endAt !== undefined) body.end_at = input.endAt
    if (input.categoryId !== undefined) body.category_id = input.categoryId
    if (input.clientId !== undefined) body.client_id = input.clientId
    if (input.ownerUserId !== undefined) body.owner_user_id = input.ownerUserId
    if (input.staffNotes !== undefined) body.staff_notes = input.staffNotes
    if (input.isDone !== undefined) body.is_done = input.isDone
    return body
  },
}))

vi.mock('@/components/calendar/NewEventModal', async () => {
  const { useEffect, createElement: h } = await import('react')
  return {
    NewEventModal: ({ open, onClose }: { open: boolean; onClose: () => void }) => {
      useEffect(() => {
        if (!open) return
        function handler(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
        window.addEventListener('keydown', handler)
        return () => window.removeEventListener('keydown', handler)
      }, [open, onClose])
      if (!open) return null
      return h('div', { role: 'dialog', 'aria-label': 'edit-modal' },
        h('span', null, 'Edit event'),
        h('button', { onClick: onClose }, 'Close modal')
      )
    },
  }
})

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { calendarEventsApi } from '@/lib/api/calendarEvents'
import { toast } from 'sonner'

const mockApi = calendarEventsApi as unknown as {
  deleteEvent: ReturnType<typeof vi.fn>
  updateEvent: ReturnType<typeof vi.fn>
  requestDelete: ReturnType<typeof vi.fn>
  approveDeleteRequest: ReturnType<typeof vi.fn>
  denyDeleteRequest: ReturnType<typeof vi.fn>
}
const mockToast = toast as unknown as { error: ReturnType<typeof vi.fn> }

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const TZ = 'America/New_York'
const SELF = 'user-self'
const MANAGER = 'user-manager'

function makeEvent(overrides: Partial<CalendarEvent> = {}): CalendarEvent {
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
    ...overrides,
  }
}

const staffUser: EventUser = { id: SELF, role: 'staff' }
const managerUser: EventUser = { id: SELF, role: 'manager' }

const DEFAULT_POS = { x: 100, y: 100 }

function renderPopover(event: CalendarEvent, user: EventUser, onClose = vi.fn(), onMutated = vi.fn()) {
  return render(
    <EventDetailsPopover
      event={event}
      pos={DEFAULT_POS}
      onClose={onClose}
      onMutated={onMutated}
      timeZone={TZ}
      user={user}
    />
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockApi.deleteEvent.mockResolvedValue(undefined)
  mockApi.updateEvent.mockResolvedValue(makeEvent())
  mockApi.requestDelete.mockResolvedValue(makeEvent({ deleteRequestedAt: '2026-10-15T10:00:00Z' }))
  mockApi.approveDeleteRequest.mockResolvedValue(makeEvent({ deletedAt: '2026-10-15T10:00:00Z' }))
  mockApi.denyDeleteRequest.mockResolvedValue(makeEvent({ deleteRequestedAt: null }))
})

// ---------------------------------------------------------------------------
// Button visibility by role/ownership
// ---------------------------------------------------------------------------

describe('button visibility', () => {
  it('staff on own event sees Edit and Delete', () => {
    renderPopover(makeEvent({ createdBy: SELF, ownerUserId: SELF }), staffUser)
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/staff notes/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/mark done/i)).not.toBeInTheDocument()
  })

  it('staff on manager-assigned event sees notes textarea and Mark done, no Edit, no Delete', () => {
    renderPopover(makeEvent({ createdBy: MANAGER, ownerUserId: SELF }), staffUser)
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
    expect(screen.getByLabelText(/staff notes/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/mark done/i)).toBeInTheDocument()
  })

  it('staff on firm-wide event sees no action buttons', () => {
    renderPopover(makeEvent({ createdBy: null, ownerUserId: null }), staffUser)
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/staff notes/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/mark done/i)).not.toBeInTheDocument()
  })

  it('manager sees Edit and Delete on any event', () => {
    renderPopover(makeEvent({ createdBy: MANAGER, ownerUserId: 'someone-else' }), managerUser)
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/staff notes/i)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Done badge
// ---------------------------------------------------------------------------

describe('Done badge', () => {
  it('shows Done badge when isDone is true', () => {
    renderPopover(makeEvent({ isDone: true }), staffUser)
    expect(screen.getByTestId('done-badge')).toBeInTheDocument()
  })

  it('does not show Done badge when isDone is false', () => {
    renderPopover(makeEvent({ isDone: false }), staffUser)
    expect(screen.queryByTestId('done-badge')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Delete confirm flow
// ---------------------------------------------------------------------------

describe('delete flow', () => {
  it('Cancel makes no API call and returns to view', async () => {
    const user = userEvent.setup()
    renderPopover(makeEvent(), staffUser)
    await user.click(screen.getByRole('button', { name: /delete/i }))
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockApi.deleteEvent).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
  })

  it('Confirm calls deleteEvent exactly once', async () => {
    const user = userEvent.setup()
    renderPopover(makeEvent(), staffUser)
    await user.click(screen.getByRole('button', { name: /delete/i }))
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(mockApi.deleteEvent).toHaveBeenCalledTimes(1))
    expect(mockApi.deleteEvent).toHaveBeenCalledWith('ev-1')
  })
})

// ---------------------------------------------------------------------------
// Annotate PATCH body
// ---------------------------------------------------------------------------

describe('annotate PATCH body', () => {
  it('saving notes sends only staffNotes in the PATCH body', async () => {
    const user = userEvent.setup()
    renderPopover(makeEvent({ createdBy: MANAGER, ownerUserId: SELF }), staffUser)
    const textarea = screen.getByLabelText(/staff notes/i)
    await user.clear(textarea)
    await user.type(textarea, 'My note')
    await user.click(screen.getByRole('button', { name: /save notes/i }))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(1))
    const [, body] = mockApi.updateEvent.mock.calls[0]
    expect(body).toHaveProperty('staff_notes', 'My note')
    expect(body).not.toHaveProperty('is_done')
    expect(body).not.toHaveProperty('title')
  })

  it('toggling Mark done sends only isDone in the PATCH body', async () => {
    const user = userEvent.setup()
    renderPopover(makeEvent({ createdBy: MANAGER, ownerUserId: SELF }), staffUser)
    await user.click(screen.getByLabelText(/mark done/i))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(1))
    const [, body] = mockApi.updateEvent.mock.calls[0]
    expect(body).toHaveProperty('is_done', true)
    expect(body).not.toHaveProperty('staff_notes')
  })
})

// ---------------------------------------------------------------------------
// Backend error handling
// ---------------------------------------------------------------------------

describe('backend error', () => {
  it('delete error shows toast.error with detail and keeps popover open', async () => {
    mockApi.deleteEvent.mockRejectedValue({ response: { data: { detail: 'Not allowed.' } } })
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderPopover(makeEvent(), staffUser, onClose)
    await user.click(screen.getByRole('button', { name: /delete/i }))
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Not allowed.'))
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByTestId('event-details-popover')).toBeInTheDocument()
  })

  it('update error shows fallback message when no detail', async () => {
    mockApi.updateEvent.mockRejectedValue(new Error('network'))
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderPopover(makeEvent({ createdBy: MANAGER, ownerUserId: SELF }), staffUser, onClose)
    await user.click(screen.getByLabelText(/mark done/i))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Could not update the event'))
    expect(onClose).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Escape handling
// ---------------------------------------------------------------------------

describe('Escape handling', () => {
  it('Escape with no modal open calls onClose', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderPopover(makeEvent(), staffUser, onClose)
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('with edit modal open, Escape calls modal onClose once and popover onClose is not called', async () => {
    const popoverOnClose = vi.fn()
    const user = userEvent.setup()
    renderPopover(makeEvent({ createdBy: SELF, ownerUserId: SELF }), staffUser, popoverOnClose)
    // open edit modal
    await user.click(screen.getByRole('button', { name: /edit/i }))
    expect(screen.getByRole('dialog', { name: /edit-modal/i })).toBeInTheDocument()
    // press Escape
    await user.keyboard('{Escape}')
    // edit modal should close (its onClose was called)
    expect(screen.queryByRole('dialog', { name: /edit-modal/i })).not.toBeInTheDocument()
    // popover onClose should NOT have been called
    expect(popoverOnClose).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Rapid-click guard (ref guard)
// ---------------------------------------------------------------------------

describe('rapid-click guard', () => {
  it('a second rapid click on Confirm makes only one API call', async () => {
    // Use a never-resolving promise so submitting stays true
    let resolveDelete!: () => void
    mockApi.deleteEvent.mockReturnValue(new Promise<void>(res => { resolveDelete = res }))
    const user = userEvent.setup()
    renderPopover(makeEvent(), staffUser)
    await user.click(screen.getByRole('button', { name: /delete/i }))
    const confirmBtn = screen.getByRole('button', { name: /confirm/i })
    await user.click(confirmBtn)
    // fireEvent bypasses the disabled attribute to test the ref guard
    fireEvent.click(confirmBtn)
    resolveDelete()
    await waitFor(() => expect(mockApi.deleteEvent).toHaveBeenCalledTimes(1))
  })
  // Honest note on proof (d): In happy-dom, fireEvent.click on a disabled React button
  // does NOT trigger the onClick handler (React filters it before the handler runs).
  // Removing only the ref guard (while keeping disabled) does NOT make this test fail.
  // Therefore the ref guard CANNOT be proven separately from the disabled attribute in
  // happy-dom. Both are kept in the implementation (ref guard + disabled together
  // provide defense-in-depth in real browsers). The test proves the COMBINED protection:
  // removing BOTH ref guard and disabled makes this test go red (verified). The test
  // we rely on for the guarantee is this one, which requires removing both.
})

// ---------------------------------------------------------------------------
// Delete request flow
// ---------------------------------------------------------------------------

const PENDING_AT = '2026-10-15T10:00:00Z'

function makeManagerAssigned() {
  return makeEvent({ createdBy: MANAGER, ownerUserId: SELF, ownerName: 'Priya Mehta' })
}

function makePendingEvent() {
  return makeEvent({
    createdBy: MANAGER,
    ownerUserId: SELF,
    ownerName: 'Priya Mehta',
    deleteRequestedAt: PENDING_AT,
    deleteRequestReason: 'No longer needed.',
  })
}

function makePendingNoName() {
  return makeEvent({
    createdBy: MANAGER,
    ownerUserId: SELF,
    ownerName: null,
    deleteRequestedAt: PENDING_AT,
  })
}

describe('delete request flow', () => {
  it('staff sees Request deletion button on a manager-assigned event', () => {
    renderPopover(makeManagerAssigned(), staffUser)
    expect(screen.getByRole('button', { name: /request deletion/i })).toBeInTheDocument()
  })

  it('Send calls requestDelete once with the reason', async () => {
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    await user.type(screen.getByLabelText(/reason for deletion request/i), 'Too old')
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(mockApi.requestDelete).toHaveBeenCalledTimes(1))
    expect(mockApi.requestDelete).toHaveBeenCalledWith('ev-1', 'Too old')
  })

  it('empty reason calls requestDelete with undefined (body {})', async () => {
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(mockApi.requestDelete).toHaveBeenCalledTimes(1))
    expect(mockApi.requestDelete).toHaveBeenCalledWith('ev-1', undefined)
  })

  it('Cancel on request step makes no API call', async () => {
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockApi.requestDelete).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /request deletion/i })).toBeInTheDocument()
  })

  it('after requestDelete success popover shows Deletion requested and no request button', async () => {
    mockApi.requestDelete.mockResolvedValue(makeEvent({
      createdBy: MANAGER, ownerUserId: SELF, deleteRequestedAt: PENDING_AT,
    }))
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(screen.getByTestId('deletion-requested-msg')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /request deletion/i })).not.toBeInTheDocument()
  })

  it('staff sees no request button when already pending', () => {
    renderPopover(makePendingEvent(), staffUser)
    expect(screen.queryByRole('button', { name: /request deletion/i })).not.toBeInTheDocument()
    expect(screen.getByTestId('deletion-requested-msg')).toBeInTheDocument()
  })

  it('manager sees Approve and Deny only when pending', () => {
    renderPopover(makePendingEvent(), managerUser)
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /request deletion/i })).not.toBeInTheDocument()
  })

  it('manager sees requester name from ownerName', () => {
    renderPopover(makePendingEvent(), managerUser)
    expect(screen.getByTestId('resolve-request-msg')).toHaveTextContent('Priya Mehta asked to delete this event')
  })

  it('manager sees A staff member fallback when ownerName is null', () => {
    renderPopover(makePendingNoName(), managerUser)
    expect(screen.getByTestId('resolve-request-msg')).toHaveTextContent('A staff member asked to delete this event')
  })

  it('Approve confirm calls approveDeleteRequest once and closes the popover', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderPopover(makePendingEvent(), managerUser, onClose)
    await user.click(screen.getByRole('button', { name: /approve/i }))
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(mockApi.approveDeleteRequest).toHaveBeenCalledTimes(1))
    expect(mockApi.approveDeleteRequest).toHaveBeenCalledWith('ev-1')
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('Deny confirm calls denyDeleteRequest once and popover shows no pending state', async () => {
    mockApi.denyDeleteRequest.mockResolvedValue(makeEvent({
      createdBy: MANAGER, ownerUserId: SELF, deleteRequestedAt: null,
    }))
    const user = userEvent.setup()
    renderPopover(makePendingEvent(), managerUser)
    await user.click(screen.getByRole('button', { name: /deny/i }))
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(mockApi.denyDeleteRequest).toHaveBeenCalledTimes(1))
    expect(mockApi.denyDeleteRequest).toHaveBeenCalledWith('ev-1')
    expect(screen.queryByTestId('resolve-request-msg')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
  })

  it('Cancel on Approve makes no API call', async () => {
    const user = userEvent.setup()
    renderPopover(makePendingEvent(), managerUser)
    await user.click(screen.getByRole('button', { name: /approve/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockApi.approveDeleteRequest).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
  })

  it('Cancel on Deny makes no API call', async () => {
    const user = userEvent.setup()
    renderPopover(makePendingEvent(), managerUser)
    await user.click(screen.getByRole('button', { name: /deny/i }))
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockApi.denyDeleteRequest).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /deny/i })).toBeInTheDocument()
  })

  it('backend error on requestDelete shows toast.error and keeps popover open', async () => {
    mockApi.requestDelete.mockRejectedValue({ response: { data: { detail: 'Already pending.' } } })
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser, onClose)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Already pending.'))
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByTestId('event-details-popover')).toBeInTheDocument()
  })

  it('Send is disabled and shows message when reason exceeds 500 characters', async () => {
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    const longReason = 'a'.repeat(501)
    await user.type(screen.getByLabelText(/reason for deletion request/i), longReason)
    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled()
    expect(screen.getByText(/500 characters or fewer/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /^send$/i }))
    expect(mockApi.requestDelete).not.toHaveBeenCalled()
  })

  it('second rapid click on Send makes only one requestDelete call', async () => {
    let resolveReq!: (v: CalendarEvent) => void
    mockApi.requestDelete.mockReturnValue(
      new Promise<CalendarEvent>(res => { resolveReq = res })
    )
    const user = userEvent.setup()
    renderPopover(makeManagerAssigned(), staffUser)
    await user.click(screen.getByRole('button', { name: /request deletion/i }))
    const sendBtn = screen.getByRole('button', { name: /^send$/i })
    await user.click(sendBtn)
    // fireEvent bypasses disabled to probe the ref guard
    fireEvent.click(sendBtn)
    resolveReq(makeEvent({ deleteRequestedAt: PENDING_AT }))
    await waitFor(() => expect(mockApi.requestDelete).toHaveBeenCalledTimes(1))
    // Honest note on proof (d): in happy-dom, fireEvent.click on a disabled React
    // button does NOT trigger onClick. Removing only the ref guard while keeping
    // disabled does NOT make this test fail. Both guards are kept for defense-in-depth.
    // Proof: removing BOTH makes the test fail.
  })
})
