// frontend/src/app/(app)/billing/[id]/page.test.tsx
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  useParams: vi.fn(() => ({ id: 'test-invoice-id' })),
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}))

vi.mock('@/lib/api', () => ({
  invoicesApi: {
    get: vi.fn(),
    send: vi.fn(),
    void: vi.fn(),
  },
  clientsApi: {
    get: vi.fn(),
  },
}))

import { invoicesApi, clientsApi } from '@/lib/api'
import type { Invoice, LineItem } from '@/lib/api/invoices'
import type { Client } from '@/lib/api/clients'

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

function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: 'client-1',
    name: 'Acme Corp',
    email: null,
    phone: null,
    companyName: null,
    addressLine1: null,
    addressLine2: null,
    city: null,
    state: null,
    postalCode: null,
    country: null,
    isActive: true,
    entityType: null,
    entitySubtype: null,
    businessDescription: null,
    clientSince: null,
    tags: [],
    notes: null,
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
    quickbooksCustomerId: null,
    portalInviteSentAt: null,
    ...overrides,
  }
}

async function renderPage() {
  const { default: InvoiceDetailPage } = await import('./page')
  return render(<InvoiceDetailPage />)
}

describe('InvoiceDetailPage line items', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(clientsApi.get).mockResolvedValue(makeClient())
  })

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
    const matches = screen.getAllByText('$800')
    expect(matches.length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('Subtotal', { selector: 'td' })).toBeInTheDocument()
  })
})

describe('InvoiceDetailPage client name', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the client name when clientsApi returns a client', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ clientId: 'client-1' }))
    vi.mocked(clientsApi.get).mockResolvedValue(makeClient({ name: 'Riverside Tax & Advisory' }))
    await renderPage()
    await waitFor(() => expect(screen.getByText('Riverside Tax & Advisory')).toBeInTheDocument())
  })

  it('renders without error when clientsApi returns null', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice())
    vi.mocked(clientsApi.get).mockResolvedValue(null as unknown as Client)
    await renderPage()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'INV-001' })).toBeInTheDocument())
  })
})

describe('InvoiceDetailPage Send/Void actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(clientsApi.get).mockResolvedValue(makeClient())
  })

  it('shows Send button for a draft invoice that has not been sent', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'draft', sentAt: null }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument())
  })

  it('does not show Send button when invoice already has sentAt', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({
      status: 'sent',
      sentAt: '2025-01-01T00:00:00Z',
    }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'INV-001' })).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /send/i })).not.toBeInTheDocument()
  })

  it('calls invoicesApi.send with the invoice id when Send is clicked', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'draft', sentAt: null }))
    vi.mocked(invoicesApi.send).mockResolvedValue(makeInvoice({ status: 'sent', sentAt: '2025-01-02T00:00:00Z' }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /send/i }))
    await waitFor(() => expect(invoicesApi.send).toHaveBeenCalledWith('test-invoice-id'))
  })

  it('shows Void button for a non-paid, non-void invoice', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'draft' }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('button', { name: /void/i })).toBeInTheDocument())
  })

  it('does not show Void button for a paid invoice', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'paid' }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'INV-001' })).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /void/i })).not.toBeInTheDocument()
  })

  it('calls invoicesApi.void after confirm', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'sent' }))
    vi.mocked(invoicesApi.void).mockResolvedValue({ updated: 1 })
    await renderPage()
    await waitFor(() => expect(screen.getByRole('button', { name: /void/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /void/i }))
    // Confirm dialog appears
    await waitFor(() => expect(screen.getByText(/void this invoice/i)).toBeInTheDocument())
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /void/i }))
    await waitFor(() =>
      expect(invoicesApi.void).toHaveBeenCalledWith('test-invoice-id')
    )
  })

  it('does not show Mark as Paid button for a void invoice', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'void' }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'INV-001' })).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /mark as paid/i })).not.toBeInTheDocument()
  })
})

describe('InvoiceDetailPage void status badge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(clientsApi.get).mockResolvedValue(makeClient())
  })

  it('shows Void label in the status badge for a void invoice, not Unknown', async () => {
    vi.mocked(invoicesApi.get).mockResolvedValue(makeInvoice({ status: 'void' }))
    await renderPage()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'INV-001' })).toBeInTheDocument())
    const badges = screen.getAllByText('Void', { selector: 'span' })
    expect(badges.length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByText('Unknown')).not.toBeInTheDocument()
  })
})
