// path: frontend/src/lib/api/calendarEvents.ts
import api from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CalendarCategory {
  id: string
  firmId: string
  name: string
  color: string
  sortOrder: number
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface CalendarEvent {
  id: string
  title: string
  startAt: string
  endAt: string
  eventTimezone: string
  categoryId: string | null
  categoryName: string | null
  categoryColor: string | null
  clientId: string | null
  clientName: string | null
  ownerUserId: string | null
  ownerName: string | null
  createdBy: string | null
  createdAt: string
  updatedAt: string
  deletedAt: string | null
}

// ---------------------------------------------------------------------------
// Mappers
// ---------------------------------------------------------------------------

export function mapCategory(raw: Record<string, unknown>): CalendarCategory {
  return {
    id: String(raw.id),
    firmId: String(raw.firm_id ?? ''),
    name: String(raw.name ?? ''),
    color: String(raw.color ?? ''),
    sortOrder: Number(raw.sort_order ?? 0),
    isActive: Boolean(raw.is_active ?? true),
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
  }
}

export function mapEvent(raw: Record<string, unknown>): CalendarEvent {
  return {
    id: String(raw.id),
    title: String(raw.title ?? ''),
    startAt: String(raw.start_at ?? ''),
    endAt: String(raw.end_at ?? ''),
    eventTimezone: String(raw.event_timezone ?? ''),
    categoryId: raw.category_id != null ? String(raw.category_id) : null,
    categoryName: raw.category_name != null ? String(raw.category_name) : null,
    categoryColor: raw.category_color != null ? String(raw.category_color) : null,
    clientId: raw.client_id != null ? String(raw.client_id) : null,
    clientName: raw.client_name != null ? String(raw.client_name) : null,
    ownerUserId: raw.owner_user_id != null ? String(raw.owner_user_id) : null,
    ownerName: raw.owner_name != null ? String(raw.owner_name) : null,
    createdBy: raw.created_by != null ? String(raw.created_by) : null,
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
    deletedAt: raw.deleted_at != null ? String(raw.deleted_at) : null,
  }
}

// ---------------------------------------------------------------------------
// Payload helpers
// ---------------------------------------------------------------------------

export function buildCategoryPayload(input: {
  name?: string
  color?: string
  sortOrder?: number
  isActive?: boolean
}): Record<string, unknown> {
  const body: Record<string, unknown> = {}
  if (input.name !== undefined) body.name = input.name
  if (input.color !== undefined) body.color = input.color
  if (input.sortOrder !== undefined) body.sort_order = input.sortOrder
  if (input.isActive !== undefined) body.is_active = input.isActive
  return body
}

export function buildEventPatch(input: {
  title?: string
  startAt?: string
  endAt?: string
  categoryId?: string | null
  clientId?: string | null
  ownerUserId?: string | null
}): Record<string, unknown> {
  const body: Record<string, unknown> = {}
  if (input.title !== undefined) body.title = input.title
  if (input.startAt !== undefined) body.start_at = input.startAt
  if (input.endAt !== undefined) body.end_at = input.endAt
  if (input.categoryId !== undefined) body.category_id = input.categoryId
  if (input.clientId !== undefined) body.client_id = input.clientId
  if (input.ownerUserId !== undefined) body.owner_user_id = input.ownerUserId
  return body
}

// ---------------------------------------------------------------------------
// Date input validation
// ---------------------------------------------------------------------------

type DateInput = Date | string

function toISOWithOffset(input: DateInput): string {
  if (input instanceof Date) {
    return input.toISOString()
  }
  if (!/Z$/.test(input) && !/[+-]\d{2}:\d{2}$/.test(input)) {
    throw new Error(`from/to must include a timezone offset. Got: ${input}`)
  }
  return input
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const calendarEventsApi = {
  // Categories

  listCategories: async (params: {
    includeInactive?: boolean
    limit?: number
    offset?: number
  } = {}): Promise<{ items: CalendarCategory[]; total: number }> => {
    const q: Record<string, unknown> = {}
    if (params.includeInactive === true) q.include_inactive = true
    if (params.limit !== undefined) q.limit = params.limit
    if (params.offset !== undefined) q.offset = params.offset
    const { data } = await api.get('/api/v1/calendar/categories', { params: q })
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return {
      items: items.map(mapCategory) as CalendarCategory[],
      total: Number(data.total ?? items.length),
    }
  },

  createCategory: async (input: {
    name: string
    color: string
    sortOrder?: number
  }): Promise<CalendarCategory> => {
    const { data } = await api.post('/api/v1/calendar/categories', buildCategoryPayload(input))
    return mapCategory(data)
  },

  updateCategory: async (
    id: string,
    input: { name?: string; color?: string; sortOrder?: number; isActive?: boolean }
  ): Promise<CalendarCategory> => {
    const { data } = await api.patch(`/api/v1/calendar/categories/${id}`, buildCategoryPayload(input))
    return mapCategory(data)
  },

  // Events

  listEvents: async (params: {
    from: DateInput
    to: DateInput
    ownerUserId?: string
    categoryId?: string
    deleted?: boolean
    limit?: number
    offset?: number
  }): Promise<{ items: CalendarEvent[]; total: number }> => {
    const q: Record<string, unknown> = {
      from: toISOWithOffset(params.from),
      to: toISOWithOffset(params.to),
    }
    if (params.ownerUserId !== undefined) q.owner_user_id = params.ownerUserId
    if (params.categoryId !== undefined) q.category_id = params.categoryId
    if (params.deleted !== undefined) q.deleted = params.deleted
    if (params.limit !== undefined) q.limit = params.limit
    if (params.offset !== undefined) q.offset = params.offset
    const { data } = await api.get('/api/v1/calendar/events', { params: q })
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return {
      items: items.map(mapEvent) as CalendarEvent[],
      total: Number(data.total ?? items.length),
    }
  },

  listEventsInRange: async (params: {
    from: DateInput
    to: DateInput
    ownerUserId?: string
    categoryId?: string
    deleted?: boolean
  }): Promise<CalendarEvent[]> => {
    // Pages by offset in steps of 100. Stops on an empty page so a wrong total can never loop forever.
    const collected: CalendarEvent[] = []
    let offset = 0
    while (true) {
      const q: Record<string, unknown> = {
        from: toISOWithOffset(params.from),
        to: toISOWithOffset(params.to),
        limit: 100,
        offset,
      }
      if (params.ownerUserId !== undefined) q.owner_user_id = params.ownerUserId
      if (params.categoryId !== undefined) q.category_id = params.categoryId
      if (params.deleted !== undefined) q.deleted = params.deleted
      const { data } = await api.get('/api/v1/calendar/events', { params: q })
      const items = Array.isArray(data) ? data : (data.items ?? [])
      const mapped = items.map(mapEvent) as CalendarEvent[]
      collected.push(...mapped)
      const total = Number(data.total ?? items.length)
      if (mapped.length === 0 || collected.length >= total) break
      offset += 100
    }
    return collected
  },

  getEvent: async (id: string): Promise<CalendarEvent> => {
    const { data } = await api.get(`/api/v1/calendar/events/${id}`)
    return mapEvent(data)
  },

  createEvent: async (input: {
    title: string
    startAt: string
    endAt: string
    categoryId?: string | null
    clientId?: string | null
    ownerUserId?: string | null
  }): Promise<CalendarEvent> => {
    const { data } = await api.post('/api/v1/calendar/events', buildEventPatch(input))
    return mapEvent(data)
  },

  updateEvent: async (
    id: string,
    input: {
      title?: string
      startAt?: string
      endAt?: string
      categoryId?: string | null
      clientId?: string | null
      ownerUserId?: string | null
    }
  ): Promise<CalendarEvent> => {
    const { data } = await api.patch(`/api/v1/calendar/events/${id}`, buildEventPatch(input))
    return mapEvent(data)
  },

  deleteEvent: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/calendar/events/${id}`)
  },

  restoreEvent: async (id: string): Promise<CalendarEvent> => {
    const { data } = await api.post(`/api/v1/calendar/events/${id}/restore`)
    return mapEvent(data)
  },
}