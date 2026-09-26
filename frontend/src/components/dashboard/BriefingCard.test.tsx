// frontend/src/components/dashboard/BriefingCard.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/lib/api/surfaceItems', () => ({
  surfaceItemsApi: {
    getBriefing: vi.fn(),
  },
}))

import { surfaceItemsApi } from '@/lib/api/surfaceItems'
import type { TierOneFact } from '@/lib/api/surfaceItems'

function makeFact(overrides: Partial<TierOneFact> = {}): TierOneFact {
  return {
    category: 'overdue_invoices',
    text: '2 invoices are overdue, with balances totaling $5,100',
    count: 2,
    amount: 5100,
    ...overrides,
  }
}

function makeBriefingResponse(facts: TierOneFact[]) {
  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    items: [{ id: 'item-1' }] as any,
    count: 1,
    resolved_in_place: 0,
    summary: '2 invoices overdue, balances totaling $5,100.',
    facts,
    intelligence_pending: true,
  }
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

async function renderCard() {
  const { BriefingCard } = await import('./BriefingCard')
  return render(<BriefingCard />, { wrapper })
}

describe('BriefingCard fact list', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders one row per fact', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([
        makeFact({ category: 'overdue_invoices', count: 2, amount: 5100 }),
        makeFact({ category: 'deadlines', text: '1 deadline with 3 open items', count: 1, amount: 3 }),
      ])
    )
    await renderCard()
    // Wait for the skeleton to be replaced by real content
    await waitFor(() => {
      const rows = document.querySelectorAll('[data-category]')
      expect(rows).toHaveLength(2)
    })
    const rows = document.querySelectorAll('[data-category]')
    expect(rows[0].getAttribute('data-category')).toBe('overdue_invoices')
    expect(rows[1].getAttribute('data-category')).toBe('deadlines')
  })

  it('renders an icon badge for overdue_invoices category', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeFact({ category: 'overdue_invoices', count: 2, amount: 5100 })])
    )
    await renderCard()
    await waitFor(() => {
      const row = document.querySelector('[data-category="overdue_invoices"]')
      expect(row).not.toBeNull()
    })
    const row = document.querySelector('[data-category="overdue_invoices"]')
    const badge = row!.querySelector('.rounded-full')
    expect(badge).not.toBeNull()
  })

  it('renders an icon badge for deadlines category', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeFact({ category: 'deadlines', count: 1, amount: 3, text: '1 deadline with 3 open items' })])
    )
    await renderCard()
    await waitFor(() => {
      expect(document.querySelector('[data-category="deadlines"]')).not.toBeNull()
    })
    const row = document.querySelector('[data-category="deadlines"]')
    const badge = row!.querySelector('.rounded-full')
    expect(badge).not.toBeNull()
  })

  it('wraps count and amount in bold markup for overdue_invoices', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeFact({ category: 'overdue_invoices', count: 2, amount: 5100 })])
    )
    await renderCard()
    await waitFor(() => {
      expect(document.querySelector('[data-category="overdue_invoices"]')).not.toBeNull()
    })
    const row = document.querySelector('[data-category="overdue_invoices"]')!
    const strongs = row.querySelectorAll('strong')
    // count (2) and amount ($5,100) both bolded
    expect(strongs.length).toBeGreaterThanOrEqual(2)
    const texts = Array.from(strongs).map((el) => el.textContent)
    expect(texts).toContain('2')
    expect(texts).toContain('$5,100')
  })

  it('wraps count AND blockers in bold for deadlines', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeFact({ category: 'deadlines', count: 1, amount: 3, text: '1 deadline with 3 open items' })])
    )
    await renderCard()
    await waitFor(() => {
      expect(document.querySelector('[data-category="deadlines"]')).not.toBeNull()
    })
    const row = document.querySelector('[data-category="deadlines"]')!
    const strongs = row.querySelectorAll('strong')
    const texts = Array.from(strongs).map((el) => el.textContent)
    expect(texts).toContain('1')
    expect(texts).toContain('3')
  })

  it('wraps only count (no amount) in bold for irs_authorizations', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeFact({ category: 'irs_authorizations', count: 1, amount: null, text: '1 IRS authorization expiring' })])
    )
    await renderCard()
    await waitFor(() => {
      expect(document.querySelector('[data-category="irs_authorizations"]')).not.toBeNull()
    })
    const row = document.querySelector('[data-category="irs_authorizations"]')!
    const strongs = row.querySelectorAll('strong')
    expect(strongs).toHaveLength(1)
    expect(strongs[0].textContent).toBe('1')
  })

  it('renders "View full briefing" link regardless of fact count', async () => {
    vi.mocked(surfaceItemsApi.getBriefing).mockResolvedValue(
      makeBriefingResponse([makeFact()])
    )
    await renderCard()
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /view full briefing/i })).toBeInTheDocument()
    )
  })
})
