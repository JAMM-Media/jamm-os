// path: frontend/src/lib/api/invoices.ts
import api from '@/lib/api'

export interface Invoice {
  id: string
  invoiceNumber: string
  clientId: string
  engagementId: string | null
  status: string
  totalAmount: number
  subtotal: number
  taxRate: number
  taxAmount: number
  dueDate: string | null
  paidAt: string | null
  sentAt: string | null
  notes: string | null
  isDeleted: boolean
  createdAt: string
  updatedAt: string
}

function mapInvoice(raw: Record<string, unknown>): Invoice {
  return {
    id: String(raw.id),
    invoiceNumber: String(raw.invoice_number ?? raw.invoiceNumber ?? ''),
    clientId: String(raw.client_id ?? raw.clientId ?? ''),
    engagementId: raw.engagement_id ? String(raw.engagement_id) : null,
    status: String(raw.status ?? 'draft'),
    totalAmount: parseFloat(String(raw.total_amount ?? raw.amount ?? '0')),
    subtotal: parseFloat(String(raw.subtotal ?? '0')),
    taxRate: parseFloat(String(raw.tax_rate ?? '0')),
    taxAmount: parseFloat(String(raw.tax_amount ?? '0')),
    dueDate: raw.due_date ? String(raw.due_date) : null,
    paidAt: raw.paid_at ? String(raw.paid_at) : null,
    sentAt: raw.sent_at ? String(raw.sent_at) : null,
    notes: raw.notes ? String(raw.notes) : null,
    isDeleted: Boolean(raw.is_deleted ?? false),
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
  }
}

export const invoicesApi = {
  list: async (
    offset = 0,
    limit = 50,
    clientId?: string
  ): Promise<{ items: Invoice[]; total: number }> => {
    const params: Record<string, unknown> = { offset, limit }
    if (clientId) params.client_id = clientId
    const { data } = await api.get('/invoices/', { params })
    const items = Array.isArray(data) ? data : (data.items ?? data.invoices ?? [])
    return {
      items: items.map(mapInvoice) as Invoice[],
      total: Number(data.total ?? items.length),
    }
  },

  get: async (id: string): Promise<Invoice> => {
    const { data } = await api.get(`/invoices/${id}`)
    return mapInvoice(data)
  },

  create: async (payload: {
    client_id: string
    engagement_id?: string
    invoice_number: string
    subtotal: number
    due_date?: string
  }): Promise<Invoice> => {
    const { data } = await api.post('/invoices/', payload)
    return mapInvoice(data)
  },

  bulkUpdate: async (ids: string[], action: 'send' | 'void'): Promise<{ updated: number }> => {
    const { data } = await api.patch('/invoices/bulk', { ids, action })
    return data
  },
}
