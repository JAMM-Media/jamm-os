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
