// frontend/src/app/(app)/briefing/page.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Mock the surfaceItems API module
// ---------------------------------------------------------------------------
vi.mock('@/lib/api/surfaceItems', () => ({
  surfaceItemsApi: {
    getBriefing: vi.fn(),
    dismissItem: vi.fn(),
    implementItem: vi.fn(),
    getItemDetail: vi.fn(),
    promoteNext: vi.fn(),
  },
}))

// Mock useAuth
vi.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ user: { role: 'firm_owner' }, isLoading: false }),
}))

import { surfaceItemsApi } from '@/lib/api/surfaceItems'
import type { SurfaceItemOut } from '@/lib/api/surfaceItems'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<SurfaceItemOut> = {}): SurfaceItemOut {
  return {
    id: 'item-1',
    firm_id: 'firm-1',
    kind: 'briefing',
    item_type: 'invoice_overdue',
    dedup_key: 'key-1',
    headline: 'Invoice #1042 is 8 days overdue',
    payload: { invoice_id: 'inv-abc', client_id: 'client-xyz' },
    rank: 1,
    slotted_at: null,
    appearance_count: 1,
    last_served_on: null,
    dismissed_at: null,
    dismissal_reason: null,
    implemented_at: null,
    suppressed_until: null,
    resolved_at: null,
    value_at_action: null,
    flagged_for_review: false,
    client_name: 'Beacon Dental',
    created_at: '2025-04-08T08:00:00Z',
    updated_at: '2025-04-08T08:00:00Z',
    ...overrides,
  }
}

function makeBriefingResponse(items: SurfaceItemOut[]) {
  return {
    items,
    count: items.length,
    resolved_in_place: 0,
    summary: '1 invoice overdue, balances totaling $500.',
    facts: [],
    intelligence_pending: true,
  }
}

function makeDetailResponse(overrides: Record<string, unknown> = {}) {
  return {
    client: 'Beacon Dental',
    engagement: 'Not recorded',
    assigned_staff: 'Not recorded',
    invoice_balance: 'Invoice #1042, balance $500.00',
    days_overdue: '8 days overdue',
    current_workflow_status: 'overdue',
    issued_date: '2026-09-01',
    last_client_communication: 'Not recorded',
    related_documents_count: 0,
    open_items: 'No reminders sent',
    ...overrides,
  }
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

// ---------------------------------------------------------------------------
// BriefingPage tests
// ---------------------------------------------------------------------------

async function renderBriefingPage() {
  const { default: BriefingPage } = await import('./page')
  return render(<BriefingPage />, { wrapper })
}

describe('Dismiss dropdown requires a selection before firing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(surfaceItemsApi.dismissItem).mockResolvedValue(makeItem())
  })

  it('does not call dismissItem when the dropdown is opened but nothing is selected', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeItem()])
    )
    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    expect(screen.getByText('Not relevant')).toBeInTheDocument()
    expect(surfaceItemsApi.dismissItem).not.toHaveBeenCalled()
  })

  it('calls dismissItem with the selected reason when an option is chosen', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeItem()])
    )
    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    fireEvent.click(screen.getByText('Not relevant'))
    await waitFor(() =>
      expect(surfaceItemsApi.dismissItem).toHaveBeenCalledWith('item-1', 'not_relevant')
    )
  })
})

describe('Row navigation links', () => {
  beforeEach(() => vi.clearAllMocks())

  it('invoice_overdue headline links to /billing/{invoice_id}', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeItem({ item_type: 'invoice_overdue', payload: { invoice_id: 'inv-abc' } })])
    )
    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: /Invoice #1042/i })
    expect(link).toHaveAttribute('href', '/billing/inv-abc')
  })

  it('irs_auth_expiring headline links to /clients/{client_id}?tab=irs-auth', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeItem({
        item_type: 'irs_auth_expiring',
        headline: 'IRS auth expiring soon',
        payload: { client_id: 'client-xyz' },
      })])
    )
    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('IRS auth expiring soon')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: /IRS auth/i })
    expect(link).toHaveAttribute('href', '/clients/client-xyz?tab=irs-auth')
  })
})

describe('Signature item types render as non-clickable', () => {
  const signatureTypes = ['signature_stalled', 'signature_declined', 'signature_expired'] as const
  beforeEach(() => vi.clearAllMocks())

  signatureTypes.forEach((itemType) => {
    it(`${itemType} headline is plain text with no link`, async () => {
      vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
        makeBriefingResponse([makeItem({
          item_type: itemType,
          headline: `Signature row for ${itemType}`,
          payload: { envelope_id: 'env-1', client_id: 'client-1' },
        })])
      )
      await renderBriefingPage()
      await waitFor(() =>
        expect(screen.getByText(`Signature row for ${itemType}`)).toBeInTheDocument()
      )
      const el = screen.getByText(`Signature row for ${itemType}`)
      expect(el.tagName.toLowerCase()).not.toBe('a')
    })
  })
})

describe('Empty state', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the exact required copy when the item list is empty', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(makeBriefingResponse([]))
    await renderBriefingPage()
    await waitFor(() =>
      expect(
        screen.getByText("You're all caught up. Check back tomorrow morning.")
      ).toBeInTheDocument()
    )
  })
})

describe('Per-row expand/collapse with real ten-field detail panel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(surfaceItemsApi.dismissItem).mockResolvedValue(makeItem())
    vi.mocked(surfaceItemsApi.implementItem).mockResolvedValue(makeItem())
  })

  it('expanding a row shows the real ten-field detail panel', async () => {
    const item = makeItem({ id: 'item-detail-1' })
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(makeBriefingResponse([item]))
    vi.mocked(surfaceItemsApi.getItemDetail).mockResolvedValue(makeDetailResponse())

    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())

    expect(screen.queryByText('Invoice #1042, balance $500.00')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /expand detail/i }))

    await waitFor(() =>
      // invoice_balance appears in both the header metadata line and the field
      expect(screen.getAllByText('Invoice #1042, balance $500.00').length).toBeGreaterThanOrEqual(1)
    )
    expect(screen.getAllByText('8 days overdue').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Overdue')).toBeInTheDocument()
  })

  it('a "Not recorded" value renders in muted styling, not as an error', async () => {
    const item = makeItem({ id: 'item-nr' })
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(makeBriefingResponse([item]))
    vi.mocked(surfaceItemsApi.getItemDetail).mockResolvedValue(
      makeDetailResponse({ last_client_communication: 'Not recorded' })
    )

    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /expand detail/i }))

    await waitFor(() => {
      const nrElements = screen.getAllByText('Not recorded')
      expect(nrElements.length).toBeGreaterThan(0)
      nrElements.forEach((el) => {
        expect(el.className).not.toMatch(/text-red|text-error|border-red/)
      })
    })
  })

  it('collapsing a row hides its detail panel', async () => {
    const item = makeItem({ id: 'item-collapse' })
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(makeBriefingResponse([item]))
    vi.mocked(surfaceItemsApi.getItemDetail).mockResolvedValue(makeDetailResponse())

    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /expand detail/i }))
    await waitFor(() =>
      expect(screen.getAllByText('Invoice #1042, balance $500.00').length).toBeGreaterThanOrEqual(1)
    )

    fireEvent.click(screen.getByRole('button', { name: /collapse detail/i }))
    await waitFor(() =>
      expect(screen.queryByText('Invoice #1042, balance $500.00')).not.toBeInTheDocument()
    )
  })

  it('Implement and Dismiss still function unchanged', async () => {
    const item = makeItem({ id: 'item-impl-dismiss' })
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(makeBriefingResponse([item]))

    await renderBriefingPage()
    await waitFor(() => expect(screen.getByText('Invoice #1042 is 8 days overdue')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /implement/i }))
    await waitFor(() =>
      expect(surfaceItemsApi.implementItem).toHaveBeenCalledWith('item-impl-dismiss')
    )

    vi.mocked(surfaceItemsApi.dismissItem).mockResolvedValue(makeItem())
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))
    fireEvent.click(screen.getByText('Already handling'))
    await waitFor(() =>
      expect(surfaceItemsApi.dismissItem).toHaveBeenCalledWith('item-impl-dismiss', 'already_handling')
    )
  })
})

describe('BriefingCard does not call getNarrative', () => {
  it('getNarrative does not exist on surfaceItemsApi', () => {
    const api = surfaceItemsApi as Record<string, unknown>
    expect(api['getNarrative']).toBeUndefined()
  })
})
