// path: frontend/src/components/notifications/DeleteRequestActions.test.tsx
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { toastMock } = vi.hoisted(() => ({
  toastMock: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('sonner', () => ({ toast: toastMock }))

vi.mock('@/lib/api/calendarEvents', () => ({
  calendarEventsApi: {
    getEvent: vi.fn(),
    approveDeleteRequest: vi.fn(),
    denyDeleteRequest: vi.fn(),
  },
}))

import { calendarEventsApi } from '@/lib/api/calendarEvents'
import { DeleteRequestActions, type DeleteRequestNotification } from './DeleteRequestActions'

const getEvent = calendarEventsApi.getEvent as unknown as ReturnType<typeof vi.fn>
const approve = calendarEventsApi.approveDeleteRequest as unknown as ReturnType<typeof vi.fn>
const deny = calendarEventsApi.denyDeleteRequest as unknown as ReturnType<typeof vi.fn>

const CREATED = '2026-10-20T18:30:00.000Z'

function notif(over: Partial<DeleteRequestNotification> = {}): DeleteRequestNotification {
  return {
    id: 'n-1',
    title: 'Delete request',
    is_read: false,
    created_at: CREATED,
    related_entity_type: 'calendar_event',
    related_entity_id: 'ev-1',
    ...over,
  }
}

function httpError(status: number, detail?: string) {
  return { response: { status, data: detail ? { detail } : {} } }
}

function pendingEvent(offsetMs = -1000) {
  return { deleteRequestedAt: new Date(Date.parse(CREATED) + offsetMs).toISOString() }
}

let qc: QueryClient

function renderIt(
  props: {
    notification?: DeleteRequestNotification
    role?: string
    onMarkRead?: (id: string) => Promise<void>
    onRowClick?: () => void
  } = {},
) {
  const onMarkRead = props.onMarkRead ?? vi.fn(async () => {})
  const onRowClick = props.onRowClick ?? vi.fn()
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={qc}>
      <div data-testid="row" onClick={onRowClick}>
        <DeleteRequestActions
          notification={props.notification ?? notif()}
          role={props.role ?? 'manager'}
          onMarkRead={onMarkRead}
        />
      </div>
    </QueryClientProvider>,
  )
  return { ...utils, onMarkRead, onRowClick }
}

beforeEach(() => {
  getEvent.mockReset()
  approve.mockReset()
  deny.mockReset()
  toastMock.success.mockReset()
  toastMock.error.mockReset()
  toastMock.info.mockReset()
  getEvent.mockResolvedValue(pendingEvent())
  approve.mockResolvedValue({})
  deny.mockResolvedValue({})
})

describe('DeleteRequestActions: who sees it', () => {
  it('staff makes zero event fetches and renders no buttons', async () => {
    renderIt({ role: 'staff' })
    await new Promise((r) => setTimeout(r, 30))
    expect(getEvent).not.toHaveBeenCalled()
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByText('Already handled')).toBeNull()
  })

  it('a row with no related_entity_id makes zero event fetches', async () => {
    renderIt({ notification: notif({ related_entity_id: undefined }) })
    await new Promise((r) => setTimeout(r, 30))
    expect(getEvent).not.toHaveBeenCalled()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('manager sees Approve and Deny when the request is pending', async () => {
    renderIt({ role: 'manager' })
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Deny' })).toBeTruthy()
    expect(getEvent).toHaveBeenCalledWith('ev-1')
  })

  it('firm_owner sees the buttons too', async () => {
    renderIt({ role: 'firm_owner' })
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeTruthy()
  })
})

describe('DeleteRequestActions: approve and deny', () => {
  it('Approve needs the confirm click before the API call', async () => {
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    expect(approve).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm approve' }))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('ev-1'))
  })

  it('Cancel backs out of the approve confirm without calling the API', async () => {
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(approve).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: 'Deny' })).toBeTruthy()
  })

  it('Deny calls the API on the first click', async () => {
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    await waitFor(() => expect(deny).toHaveBeenCalledWith('ev-1'))
  })

  it('a successful approve shows Approved and marks the row read', async () => {
    const { onMarkRead } = renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm approve' }))
    expect(await screen.findByText('Approved')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
    expect(onMarkRead).toHaveBeenCalledWith('n-1')
  })

  it('a successful deny shows Denied, marks read and invalidates the calendar and unread count', async () => {
    const { onMarkRead } = renderIt()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    expect(await screen.findByText('Denied')).toBeTruthy()
    expect(onMarkRead).toHaveBeenCalledWith('n-1')
    const keys = spy.mock.calls.map((c) => JSON.stringify((c[0] as { queryKey: unknown }).queryKey))
    expect(keys).toContain(JSON.stringify(['native-calendar-events']))
    expect(keys).toContain(JSON.stringify(['notifications-unread-count']))
  })

  it('does not call mark-read when the row is already read', async () => {
    const { onMarkRead } = renderIt({ notification: notif({ is_read: true }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    expect(await screen.findByText('Denied')).toBeTruthy()
    expect(onMarkRead).not.toHaveBeenCalled()
  })

  it('a mark-read failure leaves the status as Approved and shows no error toast', async () => {
    // A rejection from onMarkRead that escapes the component becomes an unhandled
    // rejection, so listen for one for the whole test and assert none happened.
    const unhandled = vi.fn()
    process.on('unhandledRejection', unhandled)
    try {
      const onMarkRead = vi.fn(async () => {
        throw new Error('patch failed')
      })
      renderIt({ onMarkRead })
      fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
      fireEvent.click(await screen.findByRole('button', { name: 'Confirm approve' }))
      expect(await screen.findByText('Approved')).toBeTruthy()
      await waitFor(() => expect(onMarkRead).toHaveBeenCalled())
      expect(screen.queryByText('Already handled')).toBeNull()
      expect(toastMock.error).not.toHaveBeenCalled()
      await new Promise((r) => setTimeout(r, 50))
      expect(unhandled).not.toHaveBeenCalled()
    } finally {
      process.off('unhandledRejection', unhandled)
    }
  })

  it('409 on click shows Already handled with a neutral toast and no error toast', async () => {
    deny.mockRejectedValue(httpError(409, 'No delete request is pending for this event.'))
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    expect(await screen.findByText('Already handled')).toBeTruthy()
    expect(toastMock.error).not.toHaveBeenCalled()
    expect(toastMock.info).toHaveBeenCalled()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('404 on click shows Already handled', async () => {
    approve.mockRejectedValue(httpError(404, 'Event not found.'))
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm approve' }))
    expect(await screen.findByText('Already handled')).toBeTruthy()
    expect(toastMock.error).not.toHaveBeenCalled()
  })

  it('another error keeps the buttons and shows the error toast with the detail', async () => {
    deny.mockRejectedValue(httpError(500, 'Something broke'))
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    await waitFor(() => expect(toastMock.error).toHaveBeenCalledWith('Something broke'))
    expect(screen.getByRole('button', { name: 'Deny' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Approve' })).toBeTruthy()
  })

  it('another error without a detail uses the fallback message', async () => {
    deny.mockRejectedValue(new Error('network'))
    renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    await waitFor(() =>
      expect(toastMock.error).toHaveBeenCalledWith('Could not update the event'),
    )
  })
})

describe('DeleteRequestActions: row link', () => {
  it('clicking Approve, Confirm, Cancel and Deny never triggers the row click', async () => {
    const { onRowClick } = renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm approve' }))
    await waitFor(() => expect(approve).toHaveBeenCalled())
    expect(onRowClick).not.toHaveBeenCalled()
  })

  it('clicking Deny does not trigger the row click', async () => {
    const { onRowClick } = renderIt()
    fireEvent.click(await screen.findByRole('button', { name: 'Deny' }))
    await waitFor(() => expect(deny).toHaveBeenCalled())
    expect(onRowClick).not.toHaveBeenCalled()
  })
})

describe('DeleteRequestActions: status', () => {
  it('a stale request shows Already handled with no buttons', async () => {
    getEvent.mockResolvedValue(pendingEvent(60000))
    renderIt()
    expect(await screen.findByText('Already handled')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a request cleared on the event shows Already handled', async () => {
    getEvent.mockResolvedValue({ deleteRequestedAt: null })
    renderIt()
    expect(await screen.findByText('Already handled')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a 404 on the event fetch shows Already handled, not a thrown error', async () => {
    getEvent.mockRejectedValue(httpError(404, 'Event not found.'))
    renderIt()
    expect(await screen.findByText('Already handled')).toBeTruthy()
    expect(screen.queryByText('Could not check status')).toBeNull()
  })

  it('a fetch error shows the Could not check status line and no buttons', async () => {
    getEvent.mockRejectedValue(httpError(500))
    renderIt()
    expect(await screen.findByText('Could not check status')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a 403 on the event fetch is also unavailable', async () => {
    getEvent.mockRejectedValue(httpError(403))
    renderIt()
    expect(await screen.findByText('Could not check status')).toBeTruthy()
  })

  it('an unparseable timestamp is unavailable, never pending', async () => {
    getEvent.mockResolvedValue({ deleteRequestedAt: 'not a date' })
    renderIt()
    expect(await screen.findByText('Could not check status')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
