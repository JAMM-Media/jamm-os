// frontend/src/app/(app)/billing/[id]/page.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  useParams: vi.fn(() => ({ id: 'test-invoice-id' })),
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}))

vi.mock('@/lib/api', () => ({
  invoicesApi: {
    get: vi.fn(),
  },
}))

import { invoicesApi } from '@/lib/api'
import type { Invoice, LineItem } from '@/lib/api/invoices'

function makeLineItem(overrides: Partial<LineItem> = {}): LineItem {
  return {
    description: 'Test service',
    quantity: 1,
    unitPrice: 500,
    amount: null,
    total: 500,
    ...overrides,
  }
}

function makeInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: 'test-invoice-id',
    invoiceNumber: 'INV-001',
    clientId: 'client-1',
    engagementId: null,
    status: 'draft',
    totalAmount: 1100,
    subtotal: 1100,
    taxRate: 0,
    taxAmount: 0,
    dueDate: null,
    paidAt: null,
    sentAt: null,
    notes: null,
    isDeleted: false,
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
    lineItems: [],
    ...overrides,
  }
}

async function renderPage() {
  const { default: InvoiceDetailPage } = await import('./page')
  return render(<InvoiceDetailPage />)
}

describe('InvoiceDetailPage line items', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders a table with one row per line item when lineItems is populated', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({
      lineItems: [
        makeLineItem({ description: 'Bookkeeping services', quantity: 1, unitPrice: 500, total: 500 }),
        makeLineItem({ description: 'Payroll processing', quantity: 2, unitPrice: 150, total: 300 }),
      ],
    }))
    await renderPage()
    await waitFor(() => expect(screen.getByText('Bookkeeping services')).toBeInTheDocument())
    expect(screen.getByText('Payroll processing')).toBeInTheDocument()
    expect(screen.getByText('Description')).toBeInTheDocument()
    expect(screen.getByText('Quantity')).toBeInTheDocument()
    expect(screen.getByText('Rate')).toBeInTheDocument()
    expect(screen.getByText('Amount')).toBeInTheDocument()
  })

  it('shows empty-state message and no table when lineItems is empty', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ lineItems: [] }))
    await renderPage()
    await waitFor(() =>
      expect(screen.getByText('No line items recorded for this invoice.')).toBeInTheDocument()
    )
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('subtotal row in the table uses the same invoice.subtotal value as the stat card', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({
      subtotal: 800,
      totalAmount: 800,
      lineItems: [makeLineItem({ description: 'Monthly retainer', unitPrice: 800, total: 800 })],
    }))
    await renderPage()
    await waitFor(() => expect(screen.getByText('Monthly retainer')).toBeInTheDocument())
    // $800 appears in both the Subtotal stat card and the table's subtotal row
    const matches = screen.getAllByText('$800')
    expect(matches.length).toBeGreaterThanOrEqual(2)
    // The table-row subtotal label is a <td>, not the stat card <p>
    expect(screen.getByText('Subtotal', { selector: 'td' })).toBeInTheDocument()
  })
})
