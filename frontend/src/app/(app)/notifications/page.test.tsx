// path: frontend/src/app/(app)/notifications/page.test.tsx
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({ push })),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ user: { role: 'firm_owner' }, isLoading: false }),
}))

// The page imports the axios instance as the default export of '@/lib/api'.
vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), patch: vi.fn() },
}))

import api from '@/lib/api'
import NotificationsPage from './page'

interface FakeRow {
  id: string
  title: string
  body: string
  notification_type: string
  is_read: boolean
  created_at: string
  related_entity_type?: string
  related_entity_id?: string
}

const getMock = api.get as unknown as ReturnType<typeof vi.fn>
const patchMock = api.patch as unknown as ReturnType<typeof vi.fn>

let server: FakeRow[] = []
let failSkip: number | null = null

// Local Date constructors, so the groups do not depend on the machine timezone.
function at(daysAgo: number, hour = 12): string {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() - daysAgo, hour, 0, 0).toISOString()
}

function row(i: number, over: Partial<FakeRow> = {}): FakeRow {
  return {
    id: `n-${String(i).padStart(3, '0')}`,
    title: `Title ${i}`,
    body: `Body ${i}`,
    notification_type: 'system',
    is_read: false,
    created_at: at(0),
    ...over,
  }
}

function rows(count: number): FakeRow[] {
  return Array.from({ length: count }, (_, i) => row(i))
}

function installApi() {
  getMock.mockImplementation(async (url: string) => {
    if (url.startsWith('/api/v1/notifications/unread-count')) {
      return { data: { count: server.filter((r) => !r.is_read).length } }
    }
    const u = new URL(url, 'http://test')
    const skip = Number(u.searchParams.get('skip') ?? '0')
    const limit = Number(u.searchParams.get('limit') ?? '20')
    if (failSkip !== null && skip === failSkip) throw new Error('boom')
    const items = server.slice(skip, skip + limit).map((r) => ({ ...r }))
    return { data: { items, total: server.length, limit, offset: skip } }
  })
  patchMock.mockImplementation(async (url: string) => {
    if (url.endsWith('/read-all')) {
      server.forEach((r) => { r.is_read = true })
    } else {
      const id = url.split('/')[4]
      server.forEach((r) => { if (r.id === id) r.is_read = true })
    }
    return { data: {} }
  })
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return render(<NotificationsPage />, { wrapper })
}

function rowEls(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('[data-unread]'))
}

function unreadEls(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('[data-unread="true"]'))
}

function rowFor(title: string): HTMLElement {
  const el = screen.getByText(title).closest<HTMLElement>('[data-unread]')
  if (!el) throw new Error('no row for ' + title)
  return el
}

beforeEach(() => {
  getMock.mockReset()
  patchMock.mockReset()
  push.mockClear()
  server = []
  failSkip = null
  installApi()
})

describe('notifications page: day groups', () => {
  it('renders the first page under Today, Yesterday, Last 7 days and Older headers', async () => {
    server = [
      row(0, { created_at: at(0) }),
      row(1, { created_at: at(1) }),
      row(2, { created_at: at(3) }),
      row(3, { created_at: at(10) }),
    ]
    renderPage()
    await screen.findByText('Title 0')
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toEqual(['Today', 'Yesterday', 'Last 7 days', 'Older'])
  })
})

describe('notifications page: load more', () => {
  it('shows Load more and the loaded-only note when total exceeds loaded rows, and requests skip=50', async () => {
    server = rows(120)
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(50))
    expect(screen.getByText('Load more')).toBeInTheDocument()
    expect(screen.getByText(/Showing 50 of 120 notifications/)).toBeInTheDocument()
    expect(screen.getByText(/apply to the loaded notifications only/)).toBeInTheDocument()

    fireEvent.click(screen.getByText('Load more'))
    await waitFor(() => expect(rowEls()).toHaveLength(100))
    const urls = getMock.mock.calls.map((c) => String(c[0]))
    expect(urls.some((u) => u.includes('limit=50') && u.includes('skip=50'))).toBe(true)
  })

  it('hides Load more and the note when every row is loaded', async () => {
    server = rows(3)
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(3))
    expect(screen.queryByText('Load more')).toBeNull()
    expect(screen.queryByText(/apply to the loaded notifications only/)).toBeNull()
  })

  it('dedupes rows by id when new rows shift the offsets between pages', async () => {
    server = rows(120)
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(50))
    server.unshift(row(999, { title: 'Brand new' }))
    fireEvent.click(screen.getByText('Load more'))
    await waitFor(() => expect(rowEls()).toHaveLength(99))
    const ids = new Set(rowEls().map((el) => el.textContent))
    expect(ids.size).toBe(99)
  })

  it('shows an error with Retry when a later page fails, and keeps the loaded rows', async () => {
    server = rows(120)
    failSkip = 50
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(50))
    fireEvent.click(screen.getByText('Load more'))
    await screen.findByText('Could not load more notifications.')
    expect(rowEls()).toHaveLength(50)
    failSkip = null
    fireEvent.click(screen.getByText('Retry'))
    await waitFor(() => expect(rowEls()).toHaveLength(100))
  })
})

describe('notifications page: row content', () => {
  it('shows No linked page for rows without a destination and Opens: X for rows with one', async () => {
    server = [
      row(0, { title: 'Plain system row' }),
      row(1, { title: 'IRS row', notification_type: 'irs_auth_expiry', related_entity_type: 'irs_authorization', related_entity_id: 'a-1' }),
      row(2, { title: 'Calendar row', related_entity_type: 'calendar_event', related_entity_id: 'e-1' }),
    ]
    renderPage()
    await screen.findByText('Plain system row')
    expect(screen.getAllByText('No linked page')).toHaveLength(2)
    expect(screen.getByText('Opens: Calendar')).toBeInTheDocument()
    expect(rowFor('Plain system row').className).not.toContain('cursor-pointer')
    expect(rowFor('IRS row').className).not.toContain('cursor-pointer')
    expect(rowFor('Calendar row').className).toContain('cursor-pointer')
  })

  it('marks a no-link row read on click without navigating', async () => {
    server = [row(0, { title: 'Plain system row' })]
    renderPage()
    await screen.findByText('Plain system row')
    fireEvent.click(rowFor('Plain system row'))
    await waitFor(() => expect(rowFor('Plain system row').getAttribute('data-unread')).toBe('false'))
    expect(patchMock).toHaveBeenCalledWith('/api/v1/notifications/n-000/read')
    expect(push).not.toHaveBeenCalled()
  })

  it('shows friendly type names in the dropdown, not raw codes', async () => {
    server = [row(0, { notification_type: 'lead_hot_alert' }), row(1, { notification_type: 'irs_auth_expiry' })]
    renderPage()
    await screen.findByText('Title 0')
    expect(screen.getByRole('option', { name: 'Hot lead' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'IRS authorization expiring' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'lead_hot_alert' })).toBeNull()
  })

  it('shows the delete request reason on its own labeled line and the full body untruncated', async () => {
    server = [
      row(0, {
        title: 'Delete request',
        body: 'Sam Lee has requested to delete "Team lunch". Double booked with the audit.',
        related_entity_type: 'calendar_event',
        related_entity_id: 'e-1',
      }),
    ]
    renderPage()
    await screen.findByText('Delete request')
    expect(screen.getByText('Reason:')).toBeInTheDocument()
    expect(screen.getByText(/Double booked with the audit\./)).toBeInTheDocument()
    const main = screen.getByText('Sam Lee has requested to delete "Team lunch".')
    expect(main.className).not.toContain('truncate')
  })
})

describe('notifications page: mark as read', () => {
  it('Mark all as read marks every loaded row across pages as read, then hides the button', async () => {
    server = rows(120)
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(50))
    fireEvent.click(screen.getByText('Load more'))
    await waitFor(() => expect(rowEls()).toHaveLength(100))
    expect(unreadEls()).toHaveLength(100)

    fireEvent.click(screen.getByText('Mark all as read'))
    await waitFor(() => expect(unreadEls()).toHaveLength(0))
    expect(patchMock).toHaveBeenCalledWith('/api/v1/notifications/read-all')
    await waitFor(() => expect(screen.queryByText('Mark all as read')).toBeNull())
  })

  it('shows Mark all as read when only the unread-count query reports unread items', async () => {
    server = rows(60)
    server.forEach((r, i) => { if (i < 50) r.is_read = true })
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(50))
    expect(unreadEls()).toHaveLength(0)
    await screen.findByText('Mark all as read')
  })

  it('a row marked read stays read after Load more', async () => {
    server = rows(120)
    renderPage()
    await waitFor(() => expect(rowEls()).toHaveLength(50))
    fireEvent.click(rowFor('Title 0'))
    await waitFor(() => expect(rowFor('Title 0').getAttribute('data-unread')).toBe('false'))
    fireEvent.click(screen.getByText('Load more'))
    await waitFor(() => expect(rowEls()).toHaveLength(100))
    expect(rowFor('Title 0').getAttribute('data-unread')).toBe('false')
    expect(rowFor('Title 1').getAttribute('data-unread')).toBe('true')
  })
})
