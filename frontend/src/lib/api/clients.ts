// path: frontend/src/lib/api/clients.ts
import api from '@/lib/api'

export interface Client {
  id: string
  name: string
  email: string | null
  phone: string | null
  companyName: string | null
  addressLine1: string | null
  addressLine2: string | null
  city: string | null
  state: string | null
  postalCode: string | null
  country: string | null
  isActive: boolean
  entityType: string | null
  tags: string[]
  notes: string | null
  createdAt: string
  updatedAt: string
}

export interface ClientDetail extends Client {}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface QBOARBalance {
  connected: boolean
  outstanding_balance: number | null
  last_payment_date: string | null
}

export interface ClientHealth {
  status: string
  reasons: string[]
}

function mapClient(raw: Record<string, unknown>): Client {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ''),
    email: raw.email ? String(raw.email) : null,
    phone: raw.phone ? String(raw.phone) : null,
    companyName: raw.company_name ? String(raw.company_name) : null,
    addressLine1: raw.address_line1 ? String(raw.address_line1) : null,
    addressLine2: raw.address_line2 ? String(raw.address_line2) : null,
    city: raw.city ? String(raw.city) : null,
    state: raw.state ? String(raw.state) : null,
    postalCode: raw.postal_code ? String(raw.postal_code) : null,
    country: raw.country ? String(raw.country) : null,
    isActive: Boolean(raw.is_active ?? true),
    entityType: raw.entity_type ? String(raw.entity_type) : null,
    tags: Array.isArray(raw.tags) ? (raw.tags as string[]) : [],
    notes: raw.notes ? String(raw.notes) : null,
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
  }
}

export const clientsApi = {
  list: async (offset = 0, limit = 50): Promise<{ items: Client[]; total: number }> => {
    const { data } = await api.get('/clients/', { params: { offset, limit } })
    const items = Array.isArray(data) ? data : (data.items ?? data.clients ?? [])
    return {
      items: items.map(mapClient) as Client[],
      total: Number(data.total ?? items.length),
    }
  },

  get: async (id: string): Promise<Client> => {
    const { data } = await api.get(`/clients/${id}`)
    return mapClient(data)
  },

  create: async (payload: {
    name: string
    email?: string
    phone?: string
    entity_type?: string
  }): Promise<Client> => {
    const { data } = await api.post('/clients/', payload)
    return mapClient(data)
  },

  update: async (id: string, payload: Record<string, unknown>): Promise<Client> => {
    const { data } = await api.patch(`/clients/${id}`, payload)
    return mapClient(data)
  },

  getQboAr: async (id: string): Promise<QBOARBalance> => {
    const { data } = await api.get(`/clients/${id}/qbo-ar`)
    return data as QBOARBalance
  },

  getHealth: async (id: string): Promise<ClientHealth> => {
    const { data } = await api.get(`/clients/${id}/health`)
    return data as ClientHealth
  },
}
