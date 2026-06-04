// frontend/src/lib/mock/invoices.ts

export type InvoiceStatus =
  | 'draft'
  | 'sent'
  | 'paid'
  | 'overdue'

export interface MockInvoice {
  id: string
  invoiceNumber: string
  clientId: string
  clientName: string
  engagementId: string
  engagementTitle: string
  status: InvoiceStatus
  amount: number
  issuedDate: string
  dueDate: string
}

export const mockInvoices: MockInvoice[] = [
  {
    id: 'inv1',
    invoiceNumber: 'INV-2024-001',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e1',
    engagementTitle: '2023 Tax Return — Corporate',
    status: 'sent',
    amount: 3500,
    issuedDate: '2024-07-01',
    dueDate: '2024-07-31',
  },
  {
    id: 'inv2',
    invoiceNumber: 'INV-2024-002',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e2',
    engagementTitle: 'Q2 2024 Bookkeeping',
    status: 'draft',
    amount: 1200,
    issuedDate: '2024-07-10',
    dueDate: '2024-08-10',
  },
  {
    id: 'inv3',
    invoiceNumber: 'INV-2024-003',
    clientId: '1',
    clientName: 'Acme Corp',
    engagementId: 'e3',
    engagementTitle: '2022 Tax Return — Corporate',
    status: 'paid',
    amount: 3200,
    issuedDate: '2023-09-01',
    dueDate: '2023-09-30',
  },
  {
    id: 'inv4',
    invoiceNumber: 'INV-2024-004',
    clientId: '2',
    clientName: 'Bright Future LLC',
    engagementId: 'e4',
    engagementTitle: '2023 Tax Return — Partnership',
    status: 'overdue',
    amount: 2800,
    issuedDate: '2024-06-01',
    dueDate: '2024-07-01',
  },
  {
    id: 'inv5',
    invoiceNumber: 'INV-2024-005',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e5',
    engagementTitle: '2023 Tax Return — S-Corp',
    status: 'sent',
    amount: 4100,
    issuedDate: '2024-07-05',
    dueDate: '2024-08-05',
  },
  {
    id: 'inv6',
    invoiceNumber: 'INV-2024-006',
    clientId: '3',
    clientName: 'Goldstein & Partners',
    engagementId: 'e6',
    engagementTitle: 'Q1 2024 Bookkeeping',
    status: 'paid',
    amount: 950,
    issuedDate: '2024-05-01',
    dueDate: '2024-05-31',
  },
  {
    id: 'inv7',
    invoiceNumber: 'INV-2024-007',
    clientId: '5',
    clientName: 'Ironclad Logistics',
    engagementId: 'e7',
    engagementTitle: '2023 Tax Return — LLC',
    status: 'draft',
    amount: 2200,
    issuedDate: '2024-07-20',
    dueDate: '2024-08-20',
  },
]

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}
