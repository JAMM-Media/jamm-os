// path: frontend/src/lib/api/bookings.ts
import api from '@/lib/api'

export interface Slot {
  startTime: string
  endTime: string
}

export interface Booking {
  id: string
  firmId: string
  leadId: string | null
  staffUserId: string | null
  startTime: string
  endTime: string
  status: string
  locationSnapshot: string | null
}

function mapSlot(raw: Record<string, unknown>): Slot {
  return {
    startTime: String(raw.start_time),
    endTime: String(raw.end_time),
  }
}

function mapBooking(raw: Record<string, unknown>): Booking {
  return {
    id: String(raw.id),
    firmId: String(raw.firm_id ?? ''),
    leadId: raw.lead_id ? String(raw.lead_id) : null,
    staffUserId: raw.staff_user_id ? String(raw.staff_user_id) : null,
    startTime: String(raw.start_time),
    endTime: String(raw.end_time),
    status: String(raw.status ?? ''),
    locationSnapshot: raw.location_snapshot ? String(raw.location_snapshot) : null,
  }
}

export const bookingsApi = {
  getSlots: async (staffUserId: string, startDate?: string, endDate?: string): Promise<Slot[]> => {
    const params: Record<string, string> = { staff_user_id: staffUserId }
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const { data } = await api.get('/api/v1/bookings/slots', { params })
    return Array.isArray(data) ? data.map(mapSlot) : []
  },
  create: async (payload: {
    lead_id: string
    staff_user_id: string
    start_time: string
    end_time: string
  }): Promise<Booking> => {
    const { data } = await api.post('/api/v1/bookings/', payload)
    return mapBooking(data)
  },
  listByLead: async (leadId: string): Promise<Booking[]> => {
    const { data } = await api.get('/api/v1/bookings/', { params: { lead_id: leadId } })
    return Array.isArray(data) ? data.map(mapBooking) : []
  },
}
