// path: frontend/src/components/calendar/NewEventModal.test.tsx
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, beforeEach, describe, it, expect } from 'vitest'
import { NewEventModal } from './NewEventModal'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api/calendarEvents', () => ({
  calendarEventsApi: {
    listCategories: vi.fn(),
    createEvent: vi.fn(),
    updateEvent: vi.fn(),
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

vi.mock('@/lib/api/staffApi', () => ({
  staffApi: {
    listFirmRoster: vi.fn(),
  },
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

// DatePickerPopover is tested separately; stub it to avoid portal complexity
vi.mock('@/components/calendar/DatePickerPopover', () => ({
  DatePickerPopover: ({ onPick, valueDateStr }: { onPick: (d: string) => void; valueDateStr: string; onClose: () => void; todayDateStr: string }) => (
    <div data-testid="date-picker" data-value={valueDateStr}>
      <button onClick={() => onPick('2026-02-01')}>Pick Feb 1</button>
    </div>
  ),
}))

import { calendarEventsApi } from '@/lib/api/calendarEvents'
import { staffApi } from '@/lib/api/staffApi'
import { toast } from 'sonner'

const mockApi = calendarEventsApi as unknown as {
  listCategories: ReturnType<typeof vi.fn>
  createEvent: ReturnType<typeof vi.fn>
  updateEvent: ReturnType<typeof vi.fn>
}
const mockStaffApi = staffApi as unknown as {
  listFirmRoster: ReturnType<typeof vi.fn>
}
const mockToast = toast as unknown as { error: ReturnType<typeof vi.fn>; success: ReturnType<typeof vi.fn> }

// ---------------------------------------------------------------------------
// Default props helpers
// ---------------------------------------------------------------------------

const WINTER_DATE = '2026-01-15'
const TODAY = '2026-10-12'
const TZ = 'America/New_York'
const CURRENT_USER_ID = 'user-me'

function staffProps() {
  return {
    open: true,
    onClose: vi.fn(),
    onCreated: vi.fn(),
    defaultDateStr: WINTER_DATE,
    todayDateStr: TODAY,
    timeZone: TZ,
    currentUserId: CURRENT_USER_ID,
    role: 'staff' as const,
  }
}

function managerProps() {
  return { ...staffProps(), role: 'manager' as const }
}

function ownerProps() {
  return { ...staffProps(), role: 'firm_owner' as const }
}

function mockApiSuccess() {
  mockApi.listCategories.mockResolvedValue({ items: [{ id: 'cat-1', name: 'Tax' }], total: 1 })
  mockApi.createEvent.mockResolvedValue({ id: 'ev-new', title: 'Test', startAt: '', endAt: '', deletedAt: null, staffNotes: null, completedAt: null, isDone: false, deleteRequestedAt: null, deleteRequestedBy: null, deleteRequestReason: null, categoryId: null, categoryName: null, categoryColor: null, clientId: null, clientName: null, ownerUserId: null, ownerName: null, createdBy: null, createdAt: '', updatedAt: '', eventTimezone: TZ })
  mockStaffApi.listFirmRoster.mockResolvedValue([
    { id: 'user-alice', full_name: 'Alice' },
    { id: 'user-bob', full_name: 'Bob' },
  ])
}

beforeEach(() => {
  vi.clearAllMocks()
  mockApi.listCategories.mockResolvedValue({ items: [], total: 0 })
  mockStaffApi.listFirmRoster.mockResolvedValue([])
  mockApi.createEvent.mockResolvedValue({ id: 'ev-1', title: '', startAt: '', endAt: '', deletedAt: null, staffNotes: null, completedAt: null, isDone: false, deleteRequestedAt: null, deleteRequestedBy: null, deleteRequestReason: null, categoryId: null, categoryName: null, categoryColor: null, clientId: null, clientName: null, ownerUserId: null, ownerName: null, createdBy: null, createdAt: '', updatedAt: '', eventTimezone: TZ })
})

// ---------------------------------------------------------------------------
// Field rendering
// ---------------------------------------------------------------------------

describe('field rendering', () => {
  it('renders title, date, start time, end time and category fields', async () => {
    render(<NewEventModal {...staffProps()} />)
    expect(screen.getByRole("textbox", { name: /title/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /pick event date/i })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: /start time/i })).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: /end time/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole("combobox", { name: /category/i })).toBeInTheDocument())
  })

  it('staff sees no owner select and no client field', () => {
    render(<NewEventModal {...staffProps()} />)
    expect(screen.queryByRole("combobox", { name: /owner/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("combobox", { name: /client/i })).not.toBeInTheDocument()
  })

  it('manager sees owner select defaulting to Me', async () => {
    render(<NewEventModal {...managerProps()} />)
    const ownerSelect = await screen.findByRole("combobox", { name: /owner/i })
    expect(ownerSelect).toBeInTheDocument()
    expect((ownerSelect as HTMLSelectElement).value).toBe(CURRENT_USER_ID)
  })

  it('owner and manager options include roster names', async () => {
    mockStaffApi.listFirmRoster.mockResolvedValue([
      { id: 'user-alice', full_name: 'Alice' },
      { id: 'user-bob', full_name: 'Bob' },
    ])
    render(<NewEventModal {...managerProps()} />)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Alice' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Bob' })).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Default times
// ---------------------------------------------------------------------------

describe('default times', () => {
  it('default end is start plus 60 minutes', () => {
    render(<NewEventModal {...staffProps()} />)
    const startSel = screen.getByRole("combobox", { name: /start time/i }) as HTMLSelectElement
    const endSel = screen.getByRole("combobox", { name: /end time/i }) as HTMLSelectElement
    const startVal = Number(startSel.value)
    const endVal = Number(endSel.value)
    expect(endVal - startVal).toBe(60)
  })

  it('changing start keeps the same duration when possible', () => {
    render(<NewEventModal {...staffProps()} />)
    const startSel = screen.getByRole("combobox", { name: /start time/i }) as HTMLSelectElement
    const endSel = screen.getByRole("combobox", { name: /end time/i }) as HTMLSelectElement
    const initialLength = Number(endSel.value) - Number(startSel.value)
    // move start forward by one slot (15 min)
    const newStart = Number(startSel.value) + 15
    fireEvent.change(startSel, { target: { value: String(newStart) } })
    expect(Number(endSel.value)).toBe(newStart + initialLength)
  })
})

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

describe('validation', () => {
  it('empty title shows an error and makes no API call', async () => {
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(await screen.findByText('Title is required.')).toBeInTheDocument()
    expect(mockApi.createEvent).not.toHaveBeenCalled()
  })

  it('end not after start shows an error and makes no API call', async () => {
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Test')
    const endSel = screen.getByRole("combobox", { name: /end time/i }) as HTMLSelectElement
    // set end to same as start
    const startSel = screen.getByRole("combobox", { name: /start time/i }) as HTMLSelectElement
    fireEvent.change(endSel, { target: { value: startSel.value } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(await screen.findByText('End time must be after start time.')).toBeInTheDocument()
    expect(mockApi.createEvent).not.toHaveBeenCalled()
  })

  it('spring forward time shows the daylight saving error and makes no API call', async () => {
    const user = userEvent.setup()
    render(
      <NewEventModal
        {...staffProps()}
        defaultDateStr="2026-03-08"
        todayDateStr={TODAY}
        timeZone="America/New_York"
      />
    )
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'DST test')
    // set start to 2:30 AM = 150 minutes (spring forward gap)
    const startSel = screen.getByRole("combobox", { name: /start time/i }) as HTMLSelectElement
    fireEvent.change(startSel, { target: { value: '150' } })
    // set end to something after start to pass that check
    const endSel = screen.getByRole("combobox", { name: /end time/i }) as HTMLSelectElement
    fireEvent.change(endSel, { target: { value: '180' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(await screen.findByText('That time does not exist on that date (daylight saving).')).toBeInTheDocument()
    expect(mockApi.createEvent).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Submit payloads
// ---------------------------------------------------------------------------

describe('submit payloads', () => {
  it('submit sends ISO instants converted through the firm timezone for a winter date', async () => {
    mockApiSuccess()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Winter meeting')
    // default: 2026-01-15, start 9:00 AM EST = 14:00 UTC, end 10:00 AM EST = 15:00 UTC
    const startSel = screen.getByRole("combobox", { name: /start time/i }) as HTMLSelectElement
    const endSel = screen.getByRole("combobox", { name: /end time/i }) as HTMLSelectElement
    fireEvent.change(startSel, { target: { value: '540' } })
    fireEvent.change(endSel, { target: { value: '600' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalled())
    const call = mockApi.createEvent.mock.calls[0][0]
    expect(call.startAt).toBe('2026-01-15T14:00:00.000Z')
    expect(call.endAt).toBe('2026-01-15T15:00:00.000Z')
  })

  it('staff submit sends no ownerUserId and no clientId', async () => {
    mockApiSuccess()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Staff event')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalled())
    const call = mockApi.createEvent.mock.calls[0][0]
    expect(call).not.toHaveProperty('ownerUserId')
    expect(call).not.toHaveProperty('clientId')
  })

  it('manager Me sends the current user id', async () => {
    mockApiSuccess()
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Manager event')
    // default ownerValue is currentUserId
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalled())
    const call = mockApi.createEvent.mock.calls[0][0]
    expect(call.ownerUserId).toBe(CURRENT_USER_ID)
  })

  it('manager Whole firm sends ownerUserId null', async () => {
    mockApiSuccess()
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Firm event')
    const ownerSel = await screen.findByRole("combobox", { name: /owner/i })
    fireEvent.change(ownerSel, { target: { value: '' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalled())
    const call = mockApi.createEvent.mock.calls[0][0]
    expect(call.ownerUserId).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

describe('error handling', () => {
  it('backend 422 detail is passed to toast.error and the form stays open', async () => {
    mockApi.listCategories.mockResolvedValue({ items: [], total: 0 })
    mockApi.createEvent.mockRejectedValue({
      response: { data: { detail: 'Owner must be an active user.' } },
    })
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} onClose={onClose} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Test')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Owner must be an active user.'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('inactive owner 422 detail is shown via toast', async () => {
    mockApi.listCategories.mockResolvedValue({ items: [], total: 0 })
    mockApi.createEvent.mockRejectedValue({
      response: { data: { detail: 'Cannot assign an inactive user as owner.' } },
    })
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Test')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Cannot assign an inactive user as owner.'))
  })

  it('fallback error message when backend gives no detail', async () => {
    mockApi.listCategories.mockResolvedValue({ items: [], total: 0 })
    mockApi.createEvent.mockRejectedValue(new Error('network error'))
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Test')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Could not create the event.'))
  })
})

// ---------------------------------------------------------------------------
// Success and repeat submit guard
// ---------------------------------------------------------------------------

describe('success and submit guard', () => {
  it('success calls onCreated and onClose', async () => {
    mockApiSuccess()
    const onCreated = vi.fn()
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} onCreated={onCreated} onClose={onClose} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'New event')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('a second click while submitting makes only one API call', async () => {
    let resolveCreate!: (v: unknown) => void
    mockApi.listCategories.mockResolvedValue({ items: [], total: 0 })
    mockApi.createEvent.mockReturnValue(new Promise(res => { resolveCreate = res }))
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.type(screen.getByRole("textbox", { name: /title/i }), 'Test')
    const saveBtn = screen.getByRole('button', { name: /save/i })
    await user.click(saveBtn)
    // fireEvent bypasses the disabled attribute to directly test the submitting guard
    fireEvent.click(saveBtn)
    resolveCreate({ id: 'ev-1', title: '', startAt: '', endAt: '', deletedAt: null, staffNotes: null, completedAt: null, isDone: false, deleteRequestedAt: null, deleteRequestedBy: null, deleteRequestReason: null, categoryId: null, categoryName: null, categoryColor: null, clientId: null, clientName: null, ownerUserId: null, ownerName: null, createdBy: null, createdAt: '', updatedAt: '', eventTimezone: TZ })
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalledTimes(1))
  })
})

// ---------------------------------------------------------------------------
// Date picker: Escape and pick behavior
// ---------------------------------------------------------------------------

describe('date picker interactions', () => {
  it('pressing Escape with the picker open closes the picker and leaves the modal open', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} onClose={onClose} />)
    // open picker
    await user.click(screen.getByRole('button', { name: /pick event date/i }))
    expect(screen.getByTestId('date-picker')).toBeInTheDocument()
    // press Escape
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('date-picker')).not.toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('picking a date updates the date button label and leaves the modal open', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.click(screen.getByRole('button', { name: /pick event date/i }))
    await user.click(screen.getByRole('button', { name: /pick feb 1/i }))
    expect(screen.getByRole('button', { name: /pick event date/i })).toHaveTextContent('2026-02-01')
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.queryByTestId('date-picker')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Edit mode (editEvent prop)
// ---------------------------------------------------------------------------

describe('edit mode', () => {
  const EDIT_EVENT: import('@/lib/api/calendarEvents').CalendarEvent = {
    id: 'ev-edit',
    title: 'Morning sync',
    startAt: '2026-01-15T14:00:00Z',
    endAt: '2026-01-15T15:00:00Z',
    eventTimezone: TZ,
    categoryId: 'cat-1',
    categoryName: 'Tax',
    categoryColor: null,
    clientId: null,
    clientName: null,
    ownerUserId: CURRENT_USER_ID,
    ownerName: 'Me',
    createdBy: CURRENT_USER_ID,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    deletedAt: null,
    staffNotes: null,
    completedAt: null,
    isDone: false,
    deleteRequestedAt: null,
    deleteRequestedBy: null,
    deleteRequestReason: null,
  }

  it('edit mode title reads "Edit event"', async () => {
    mockApiSuccess()
    render(<NewEventModal {...staffProps()} editEvent={EDIT_EVENT} />)
    expect(await screen.findByText('Edit event')).toBeInTheDocument()
  })

  it('edit mode prefills title and times in the firm timezone', async () => {
    mockApiSuccess()
    render(<NewEventModal {...staffProps()} editEvent={EDIT_EVENT} />)
    const titleInput = screen.getByRole('textbox', { name: /title/i }) as HTMLInputElement
    expect(titleInput.value).toBe('Morning sync')
    // 2026-01-15T14:00:00Z in America/New_York (EST, UTC-5) = 09:00 = 540 minutes
    const startSel = screen.getByRole('combobox', { name: /start time/i }) as HTMLSelectElement
    expect(startSel.value).toBe('540')
    // end: 2026-01-15T15:00:00Z = 10:00 EST = 600 minutes
    const endSel = screen.getByRole('combobox', { name: /end time/i }) as HTMLSelectElement
    expect(endSel.value).toBe('600')
  })

  it('edit mode sends only changed fields via updateEvent', async () => {
    mockApi.listCategories.mockResolvedValue({ items: [{ id: 'cat-1', name: 'Tax' }], total: 1 })
    mockApi.updateEvent.mockResolvedValue({ ...EDIT_EVENT, title: 'New title' })
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} editEvent={EDIT_EVENT} />)
    const titleInput = screen.getByRole('textbox', { name: /title/i })
    await user.clear(titleInput)
    await user.type(titleInput, 'New title')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(1))
    const [id, patch] = mockApi.updateEvent.mock.calls[0]
    expect(id).toBe('ev-edit')
    expect(patch).toHaveProperty('title', 'New title')
    // unchanged fields must NOT be in the patch
    expect(patch).not.toHaveProperty('start_at')
    expect(patch).not.toHaveProperty('end_at')
    expect(patch).not.toHaveProperty('category_id')
  })
})

// ---------------------------------------------------------------------------
// Client picker (Calendar 3e)
// ---------------------------------------------------------------------------

// Hoisted by vitest to the top of the file, so it applies to every test here.
vi.mock('@/lib/api/clients', () => ({
  clientsApi: {
    list: vi.fn(),
  },
}))

import { clientsApi } from '@/lib/api/clients'

const mockClientsApi = clientsApi as unknown as { list: ReturnType<typeof vi.fn> }

// Load-bearing for the existing manager and owner tests: without a resolved
// value the mocked list() returns undefined and the load effect throws.
beforeEach(() => {
  mockClientsApi.list.mockResolvedValue({ items: [], total: 0 })
})

describe('client picker', () => {
  const CLIENTS = {
    items: [
      { id: 'client-1', name: 'Acme LLC', isActive: true },
      { id: 'client-2', name: 'Old Co', isActive: false },
      { id: 'client-3', name: 'Beta Inc', isActive: true },
    ],
    total: 3,
  }

  function clientEditEvent(overrides: Partial<import('@/lib/api/calendarEvents').CalendarEvent> = {}): import('@/lib/api/calendarEvents').CalendarEvent {
    return {
      id: 'ev-client',
      title: 'Client review',
      startAt: '2026-01-15T14:00:00Z',
      endAt: '2026-01-15T15:00:00Z',
      eventTimezone: TZ,
      categoryId: null,
      categoryName: null,
      categoryColor: null,
      clientId: 'client-1',
      clientName: 'Acme LLC',
      ownerUserId: CURRENT_USER_ID,
      ownerName: 'Me',
      createdBy: CURRENT_USER_ID,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
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

  it('manager sees the Client select with No client first and active clients only', async () => {
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    render(<NewEventModal {...managerProps()} />)
    const sel = await screen.findByRole('combobox', { name: /client/i }) as HTMLSelectElement
    expect(sel.value).toBe('')
    expect(screen.getByRole('option', { name: 'No client' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('option', { name: 'Acme LLC' })).toBeInTheDocument())
    expect(screen.getByRole('option', { name: 'Beta Inc' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Old Co' })).not.toBeInTheDocument()
    expect(mockClientsApi.list).toHaveBeenCalledWith(0, 1000)
  })

  it('owner sees the Client select', async () => {
    render(<NewEventModal {...ownerProps()} />)
    expect(await screen.findByRole('combobox', { name: /client/i })).toBeInTheDocument()
  })

  it('staff does not see the Client select and the clients list is not requested', () => {
    render(<NewEventModal {...staffProps()} />)
    expect(screen.queryByRole('combobox', { name: /client/i })).not.toBeInTheDocument()
    expect(mockClientsApi.list).not.toHaveBeenCalled()
  })

  it('staff submit sends no clientId', async () => {
    mockApiSuccess()
    const user = userEvent.setup()
    render(<NewEventModal {...staffProps()} />)
    await user.type(screen.getByRole('textbox', { name: /title/i }), 'Staff event')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalledTimes(1))
    expect(mockApi.createEvent.mock.calls[0][0]).not.toHaveProperty('clientId')
  })

  it('manager picks a client and create sends that clientId', async () => {
    mockApiSuccess()
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} />)
    await user.type(screen.getByRole('textbox', { name: /title/i }), 'Client meeting')
    await waitFor(() => expect(screen.getByRole('option', { name: 'Acme LLC' })).toBeInTheDocument())
    fireEvent.change(screen.getByRole('combobox', { name: /client/i }), { target: { value: 'client-1' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalledTimes(1))
    expect(mockApi.createEvent.mock.calls[0][0]).toHaveProperty('clientId', 'client-1')
  })

  it('manager leaving No client sends no clientId on create', async () => {
    mockApiSuccess()
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} />)
    await user.type(screen.getByRole('textbox', { name: /title/i }), 'No client meeting')
    await waitFor(() => expect(screen.getByRole('option', { name: 'Acme LLC' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalledTimes(1))
    expect(mockApi.createEvent.mock.calls[0][0]).not.toHaveProperty('clientId')
  })

  it('edit mode prefills the existing client', async () => {
    mockApiSuccess()
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    render(<NewEventModal {...managerProps()} editEvent={clientEditEvent()} />)
    const sel = await screen.findByRole('combobox', { name: /client/i }) as HTMLSelectElement
    await waitFor(() => expect(sel.value).toBe('client-1'))
    await waitFor(() => expect(screen.getByRole('option', { name: 'Beta Inc' })).toBeInTheDocument())
    expect(sel.value).toBe('client-1')
    expect(screen.getAllByRole('option', { name: 'Acme LLC' })).toHaveLength(1)
  })

  it('edit mode sends client_id only when the client changed', async () => {
    mockApiSuccess()
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    mockApi.updateEvent.mockResolvedValue(clientEditEvent({ title: 'Renamed' }))
    const user = userEvent.setup()
    const first = render(<NewEventModal {...managerProps()} editEvent={clientEditEvent()} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'Beta Inc' })).toBeInTheDocument())
    const titleInput = screen.getByRole('textbox', { name: /title/i })
    await user.clear(titleInput)
    await user.type(titleInput, 'Renamed')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(1))
    const [, unchangedPatch] = mockApi.updateEvent.mock.calls[0]
    expect(unchangedPatch).toHaveProperty('title', 'Renamed')
    expect(unchangedPatch).not.toHaveProperty('client_id')
    first.unmount()

    mockApi.updateEvent.mockResolvedValue(clientEditEvent({ clientId: 'client-3', clientName: 'Beta Inc' }))
    render(<NewEventModal {...managerProps()} editEvent={clientEditEvent()} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'Beta Inc' })).toBeInTheDocument())
    fireEvent.change(screen.getByRole('combobox', { name: /client/i }), { target: { value: 'client-3' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(2))
    const [, changedPatch] = mockApi.updateEvent.mock.calls[1]
    expect(changedPatch).toEqual({ client_id: 'client-3' })
  })

  it('clearing the client in edit mode sends client_id null', async () => {
    mockApiSuccess()
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    mockApi.updateEvent.mockResolvedValue(clientEditEvent({ clientId: null, clientName: null }))
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} editEvent={clientEditEvent()} />)
    await waitFor(() => expect(screen.getByRole('option', { name: 'Beta Inc' })).toBeInTheDocument())
    fireEvent.change(screen.getByRole('combobox', { name: /client/i }), { target: { value: '' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(1))
    const [, patch] = mockApi.updateEvent.mock.calls[0]
    expect(patch).toHaveProperty('client_id', null)
  })

  it('editing an event whose clientId is undefined and changing only the title sends no client_id', async () => {
    mockApiSuccess()
    mockApi.updateEvent.mockResolvedValue(clientEditEvent({ title: 'Renamed', clientId: null, clientName: null }))
    const user = userEvent.setup()
    const legacyEvent = clientEditEvent({ clientId: undefined as unknown as null, clientName: null })
    render(<NewEventModal {...managerProps()} editEvent={legacyEvent} />)
    await screen.findByRole('combobox', { name: /client/i })
    const titleInput = screen.getByRole('textbox', { name: /title/i })
    await user.clear(titleInput)
    await user.type(titleInput, 'Renamed')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.updateEvent).toHaveBeenCalledTimes(1))
    const [, patch] = mockApi.updateEvent.mock.calls[0]
    expect(patch).toHaveProperty('title', 'Renamed')
    expect(patch).not.toHaveProperty('client_id')
  })

  it('clients list failure leaves only No client and the form still submits', async () => {
    mockApiSuccess()
    mockClientsApi.list.mockRejectedValue(new Error('network'))
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} />)
    const sel = await screen.findByRole('combobox', { name: /client/i }) as HTMLSelectElement
    await waitFor(() => expect(mockClientsApi.list).toHaveBeenCalledTimes(1))
    expect(sel.querySelectorAll('option')).toHaveLength(1)
    expect(screen.getByRole('option', { name: 'No client' })).toBeInTheDocument()
    await user.type(screen.getByRole('textbox', { name: /title/i }), 'Still works')
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockApi.createEvent).toHaveBeenCalledTimes(1))
    expect(mockApi.createEvent.mock.calls[0][0]).not.toHaveProperty('clientId')
  })

  it('backend 422 detail on a client submit is shown via toast.error and the form stays open', async () => {
    mockClientsApi.list.mockResolvedValue(CLIENTS)
    mockApi.createEvent.mockRejectedValue({ response: { data: { detail: 'Client not found.' } } })
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<NewEventModal {...managerProps()} onClose={onClose} />)
    await user.type(screen.getByRole('textbox', { name: /title/i }), 'Bad client')
    await waitFor(() => expect(screen.getByRole('option', { name: 'Acme LLC' })).toBeInTheDocument())
    fireEvent.change(screen.getByRole('combobox', { name: /client/i }), { target: { value: 'client-1' } })
    await user.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(mockToast.error).toHaveBeenCalledWith('Client not found.'))
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('combobox', { name: /client/i })).toBeInTheDocument()
  })
})
