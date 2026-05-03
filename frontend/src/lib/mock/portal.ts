// frontend/src/lib/mock/portal.ts

export interface PortalActionItem {
  id: string
  type: 'document-request' | 'signature' | 'invoice'
  title: string
  description: string
  dueDate?: string
  completed: boolean
}

export interface PortalDocument {
  id: string
  name: string
  uploadedAt: string
  fileType: string
  fileSizeKb: number
  uploadedBy: 'client' | 'firm'
}

export interface PortalInvoice {
  id: string
  invoiceNumber: string
  amount: number
  status: 'unpaid' | 'paid'
  dueDate: string
  issuedDate: string
}

export const portalClient = {
  name: 'James Holden',
  firmName: 'Miller & Associates CPA',
}

export const portalActionItems: PortalActionItem[] = [
  {
    id: 'pa1',
    type: 'document-request',
    title: 'Upload 2023 W-2 Forms',
    description: 'Please upload all W-2 forms received for the 2023 tax year.',
    dueDate: '2024-08-15',
    completed: false,
  },
  {
    id: 'pa2',
    type: 'document-request',
    title: 'Upload Bank Statements — Q2 2024',
    description: 'All business bank statements for April, May, and June 2024.',
    dueDate: '2024-08-01',
    completed: false,
  },
  {
    id: 'pa3',
    type: 'signature',
    title: 'Sign Engagement Letter',
    description: 'Please review and sign the 2023 tax return engagement letter.',
    dueDate: '2024-07-25',
    completed: false,
  },
  {
    id: 'pa4',
    type: 'invoice',
    title: 'Pay Invoice INV-2024-001',
    description: '$3,500 due for 2023 Corporate Tax Return preparation.',
    dueDate: '2024-07-31',
    completed: false,
  },
  {
    id: 'pa5',
    type: 'document-request',
    title: 'Upload 2022 Prior Year Return',
    description: 'Copy of your 2022 filed tax return for reference.',
    dueDate: '2024-07-10',
    completed: true,
  },
  {
    id: 'pa6',
    type: 'signature',
    title: 'Sign Prior Year Amendment',
    description: 'Signature required on the 2021 amended return.',
    completed: true,
  },
]

export const portalDocuments: PortalDocument[] = [
  {
    id: 'pd1',
    name: 'Engagement Letter — 2023 Tax Return',
    uploadedAt: '2024-01-20',
    fileType: 'PDF',
    fileSizeKb: 89,
    uploadedBy: 'firm',
  },
  {
    id: 'pd2',
    name: '2022 Tax Return (Filed Copy)',
    uploadedAt: '2024-07-10',
    fileType: 'PDF',
    fileSizeKb: 412,
    uploadedBy: 'client',
  },
  {
    id: 'pd3',
    name: '2023 W-2 — Acme Corp',
    uploadedAt: '2024-07-14',
    fileType: 'PDF',
    fileSizeKb: 142,
    uploadedBy: 'client',
  },
]

export const portalInvoices: PortalInvoice[] = [
  {
    id: 'pi1',
    invoiceNumber: 'INV-2024-001',
    amount: 3500,
    status: 'unpaid',
    dueDate: '2024-07-31',
    issuedDate: '2024-07-01',
  },
  {
    id: 'pi2',
    invoiceNumber: 'INV-2023-008',
    amount: 3200,
    status: 'paid',
    dueDate: '2023-09-30',
    issuedDate: '2023-09-01',
  },
]

export function formatCurrencyPortal(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}
