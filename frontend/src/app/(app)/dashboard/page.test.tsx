// frontend/src/app/(app)/dashboard/page.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api/dashboard', () => ({
  dashboardApi: {
    getMetrics: vi.fn(),
    getSections: vi.fn(),
    updateSections: vi.fn(),
  },
}))

vi.mock('next/navigation', () => ({
  useParams: vi.fn(() => ({})),
  useRouter: vi.fn(() => ({ push: vi.fn() })),
  usePathname: vi.fn(() => '/dashboard'),
}))

vi.mock('@/components/dashboard/BriefingCard', () => ({
  BriefingCard: () => <div data-testid="briefing-card" />,
}))

import { dashboardApi } from '@/lib/api/dashboard'
import type { DashboardSectionItem } from '@/lib/api/dashboard'

function makeMetrics(overrides = {}) {
  return {
    mrr: 0,
    mrr_invoice_count: 0,
    mrr_trend_pct: null,
    mrr_trend_direction: null,
    outstanding_ar: 0,
    outstanding_ar_count: 0,
    oldest_overdue_days: null,
    ar_trend_pct: null,
    ar_trend_direction: null,
    wip_value: 0,
    wip_hours: 0,
    wip_trend_pct: null,
    wip_trend_direction: null,
    overdue_engagement_count: 0,
    overdue_engagements: [],
    upcoming_deadlines: [],
    staff_utilization: [],
    unsigned_document_count: 0,
    unsigned_documents: [],
    top_engagements: [],
    ...overrides,
  }
}

function makeStaff(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    user_id: `user-${i}`,
    full_name: `Staff ${i + 1}`,
    hours_this_week: i * 4,
    utilization_pct: Math.min((i + 1) * 12, 100),
  }))
}

const STAFF_ONLY: DashboardSectionItem[] = [
  { key: 'staff_utilization', visible: true, order: 0 },
]

async function renderPage() {
  const { default: DashboardPage } = await import('./page')
  return render(<DashboardPage />)
}

describe('StaffUtilization preview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(dashboardApi.getSections).mockResolvedValue(STAFF_ONLY)
  })

  it('shows only 5 rows when staff count exceeds the preview limit', async () => {
    vi.mocked(dashboardApi.getMetrics).mockResolvedValue(makeMetrics({
      staff_utilization: makeStaff(8),
    }))
    await renderPage()
    await waitFor(() => expect(screen.getByText('Staff 1')).toBeInTheDocument())

    expect(screen.getByText('Staff 5')).toBeInTheDocument()
    expect(screen.queryByText('Staff 6')).not.toBeInTheDocument()
    expect(screen.getByText('View all 8 staff')).toBeInTheDocument()
  })

  it('reveals all staff when the expand button is clicked', async () => {
    vi.mocked(dashboardApi.getMetrics).mockResolvedValue(makeMetrics({
      staff_utilization: makeStaff(8),
    }))
    await renderPage()
    await waitFor(() => expect(screen.getByText('Staff 1')).toBeInTheDocument())

    fireEvent.click(screen.getByText('View all 8 staff'))

    expect(screen.getByText('Staff 6')).toBeInTheDocument()
    expect(screen.getByText('Staff 8')).toBeInTheDocument()
    expect(screen.getByText('Show fewer')).toBeInTheDocument()
  })

  it('shows all rows with no expand button when staff is at or below the preview limit', async () => {
    vi.mocked(dashboardApi.getMetrics).mockResolvedValue(makeMetrics({
      staff_utilization: makeStaff(3),
    }))
    await renderPage()
    await waitFor(() => expect(screen.getByText('Staff 3')).toBeInTheDocument())

    expect(screen.queryByText(/View all/)).not.toBeInTheDocument()
  })
})
