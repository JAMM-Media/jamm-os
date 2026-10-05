// path: frontend/src/lib/api/calendarEvents.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import api from '@/lib/api'
import {
  mapCategory,
  mapEvent,
  buildCategoryPayload,
  buildEventPatch,
  calendarEventsApi,
} from './calendarEvents'

vi.mock('@/lib/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  patch: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function rawCat(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'cat-1',
    firm_id: 'firm-1',
    name: 'Advisory',
    color: '#FF0000',
    sort_order: 2,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    ...overrides,
  }
}

function rawEv(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'ev-1',
    title: 'Client Call',
    start_at: '2026-10-15T14:00:00Z',
    end_at: '2026-10-15T15:00:00Z',
    event_timezone: 'America/New_York',
    category_id: 'cat-1',
    category_name: 'Advisory',
    category_color: '#FF0000',
    client_id: 'cli-1',
    client_name: 'Acme',
    owner_user_id: 'usr-1',
    owner_name: 'Alice',
    created_by: 'usr-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
    deleted_at: null,
    ...overrides,
  }
}

const FROM = '2026-10-01T00:00:00Z'
const TO = '2026-10-31T23:59:59Z'

// ---------------------------------------------------------------------------
// mapCategory
// ---------------------------------------------------------------------------

describe('mapCategory', () => {
  it('maps all fields', () => {
    const cat = mapCategory(rawCat())
    expect(cat.id).toBe('cat-1')
    expect(cat.firmId).toBe('firm-1')
    expect(cat.name).toBe('Advisory')
    expect(cat.color).toBe('#FF0000')
    expect(cat.sortOrder).toBe(2)
    expect(cat.isActive).toBe(true)
    expect(cat.createdAt).toBe('2026-01-01T00:00:00Z')
    expect(cat.updatedAt).toBe('2026-01-02T00:00:00Z')
  })
})

// ---------------------------------------------------------------------------
// mapEvent
// ---------------------------------------------------------------------------

describe('mapEvent', () => {
  it('maps all fields', () => {
    const ev = mapEvent(rawEv())
    expect(ev.id).toBe('ev-1')
    expect(ev.title).toBe('Client Call')
    expect(ev.startAt).toBe('2026-10-15T14:00:00Z')
    expect(ev.endAt).toBe('2026-10-15T15:00:00Z')
    expect(ev.eventTimezone).toBe('America/New_York')
    expect(ev.categoryId).toBe('cat-1')
    expect(ev.categoryName).toBe('Advisory')
    expect(ev.categoryColor).toBe('#FF0000')
    expect(ev.clientId).toBe('cli-1')
    expect(ev.clientName).toBe('Acme')
    expect(ev.ownerUserId).toBe('usr-1')
    expect(ev.ownerName).toBe('Alice')
    expect(ev.createdBy).toBe('usr-1')
    expect(ev.createdAt).toBe('2026-01-01T00:00:00Z')
    expect(ev.updatedAt).toBe('2026-01-02T00:00:00Z')
    expect(ev.deletedAt).toBeNull()
  })

  it('maps missing nullable fields to null', () => {
    const ev = mapEvent(rawEv({
      category_id: null,
      category_name: null,
      category_color: null,
      client_id: null,
      client_name: null,
      owner_user_id: null,
      owner_name: null,
      deleted_at: null,
    }))
    expect(ev.categoryId).toBeNull()
    expect(ev.categoryName).toBeNull()
    expect(ev.categoryColor).toBeNull()
    expect(ev.clientId).toBeNull()
    expect(ev.clientName).toBeNull()
    expect(ev.ownerUserId).toBeNull()
    expect(ev.ownerName).toBeNull()
    expect(ev.deletedAt).toBeNull()
  })

  it('maps absent nullable fields to null', () => {
    const ev = mapEvent({ id: 'x', title: 'T', start_at: 's', end_at: 'e', event_timezone: 'UTC', created_by: 'u', created_at: 'c', updated_at: 'u2' })
    expect(ev.categoryId).toBeNull()
    expect(ev.categoryName).toBeNull()
    expect(ev.categoryColor).toBeNull()
    expect(ev.clientId).toBeNull()
    expect(ev.clientName).toBeNull()
    expect(ev.ownerUserId).toBeNull()
    expect(ev.ownerName).toBeNull()
    expect(ev.deletedAt).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// buildCategoryPayload
// ---------------------------------------------------------------------------

describe('buildCategoryPayload', () => {
  it('omits undefined keys', () => {
    expect(buildCategoryPayload({})).toEqual({})
  })

  it('includes provided keys in snake_case', () => {
    const body = buildCategoryPayload({ name: 'X', color: '#000', sortOrder: 3, isActive: false })
    expect(body).toEqual({ name: 'X', color: '#000', sort_order: 3, is_active: false })
  })

  it('omits only the keys not given', () => {
    const body = buildCategoryPayload({ name: 'Y' })
    expect(body).toHaveProperty('name', 'Y')
    expect(body).not.toHaveProperty('color')
    expect(body).not.toHaveProperty('sort_order')
    expect(body).not.toHaveProperty('is_active')
  })
})

// ---------------------------------------------------------------------------
// buildEventPatch
// ---------------------------------------------------------------------------

describe('buildEventPatch', () => {
  it('omits undefined keys', () => {
    expect(buildEventPatch({})).toEqual({})
  })

  it('keeps null for categoryId, clientId and ownerUserId', () => {
    const body = buildEventPatch({ categoryId: null, clientId: null, ownerUserId: null })
    expect(body).toHaveProperty('category_id', null)
    expect(body).toHaveProperty('client_id', null)
    expect(body).toHaveProperty('owner_user_id', null)
  })

  it('keeps real string values', () => {
    const body = buildEventPatch({ title: 'Meeting', categoryId: 'cat-1' })
    expect(body).toHaveProperty('title', 'Meeting')
    expect(body).toHaveProperty('category_id', 'cat-1')
  })

  it('omits categoryId key when undefined', () => {
    const body = buildEventPatch({ title: 'Only title' })
    expect(body).not.toHaveProperty('category_id')
  })
})

// ---------------------------------------------------------------------------
// updateEvent body
// ---------------------------------------------------------------------------

describe('calendarEventsApi.updateEvent', () => {
  it('sends category_id null when categoryId is null', async () => {
    mockApi.patch.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.updateEvent('ev-1', { categoryId: null })
    expect(mockApi.patch).toHaveBeenCalledWith(
      '/api/v1/calendar/events/ev-1',
      expect.objectContaining({ category_id: null })
    )
  })

  it('omits category_id from body when categoryId is undefined', async () => {
    mockApi.patch.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.updateEvent('ev-1', { title: 'New title' })
    const body = mockApi.patch.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('category_id')
  })
})

// ---------------------------------------------------------------------------
// deleteEvent
// ---------------------------------------------------------------------------

describe('calendarEventsApi.deleteEvent', () => {
  it('resolves on 204 response with no body', async () => {
    mockApi.delete.mockResolvedValue({ status: 204, data: undefined })
    await expect(calendarEventsApi.deleteEvent('ev-1')).resolves.toBeUndefined()
    expect(mockApi.delete).toHaveBeenCalledWith('/api/v1/calendar/events/ev-1')
  })
})

// ---------------------------------------------------------------------------
// listEvents query params
// ---------------------------------------------------------------------------

describe('calendarEventsApi.listEvents', () => {
  it('sends from, to, owner_user_id, category_id, deleted, limit and offset', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listEvents({
      from: FROM,
      to: TO,
      ownerUserId: 'usr-1',
      categoryId: 'cat-1',
      deleted: true,
      limit: 25,
      offset: 50,
    })
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/calendar/events', {
      params: {
        from: FROM,
        to: TO,
        owner_user_id: 'usr-1',
        category_id: 'cat-1',
        deleted: true,
        limit: 25,
        offset: 50,
      },
    })
  })

  it('omits optional params when not provided', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listEvents({ from: FROM, to: TO })
    const params = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    expect(params).not.toHaveProperty('owner_user_id')
    expect(params).not.toHaveProperty('category_id')
    expect(params).not.toHaveProperty('deleted')
    expect(params).not.toHaveProperty('limit')
    expect(params).not.toHaveProperty('offset')
  })

  it('sends a Date as an ISO string with offset', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    const d = new Date('2026-10-01T00:00:00Z')
    await calendarEventsApi.listEvents({ from: d, to: TO })
    const params = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    expect(typeof params.from).toBe('string')
    expect(params.from as string).toMatch(/Z$/)
  })

  it('throws for a naive ISO string without timezone offset', async () => {
    await expect(
      calendarEventsApi.listEvents({ from: '2026-10-05T09:00:00', to: TO })
    ).rejects.toThrow('timezone offset')
    expect(mockApi.get).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// listEventsInRange pagination
// ---------------------------------------------------------------------------

describe('calendarEventsApi.listEventsInRange', () => {
  it('makes three calls for totals of 100, 100, 30 and returns all 230 items', async () => {
    const makeItems = (count: number) =>
      Array.from({ length: count }, (_, i) => rawEv({ id: String(i) }))

    mockApi.get
      .mockResolvedValueOnce({ data: { items: makeItems(100), total: 230 } })
      .mockResolvedValueOnce({ data: { items: makeItems(100), total: 230 } })
      .mockResolvedValueOnce({ data: { items: makeItems(30), total: 230 } })

    const result = await calendarEventsApi.listEventsInRange({ from: FROM, to: TO })
    expect(result).toHaveLength(230)
    expect(mockApi.get).toHaveBeenCalledTimes(3)
  })

  it('stops when a page returns empty even if total is larger', async () => {
    const makeItems = (count: number) =>
      Array.from({ length: count }, (_, i) => rawEv({ id: String(i) }))

    mockApi.get
      .mockResolvedValueOnce({ data: { items: makeItems(100), total: 500 } })
      .mockResolvedValueOnce({ data: { items: [], total: 500 } })

    const result = await calendarEventsApi.listEventsInRange({ from: FROM, to: TO })
    expect(result).toHaveLength(100)
    expect(mockApi.get).toHaveBeenCalledTimes(2)
  })
})

// ---------------------------------------------------------------------------
// listCategories
// ---------------------------------------------------------------------------

describe('calendarEventsApi.listCategories', () => {
  it('sends include_inactive when true', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listCategories({ includeInactive: true })
    const params = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    expect(params).toHaveProperty('include_inactive', true)
  })

  it('omits include_inactive when not provided', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listCategories({})
    const params = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    expect(params).not.toHaveProperty('include_inactive')
  })

  it('omits include_inactive when false', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listCategories({ includeInactive: false })
    const params = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    expect(params).not.toHaveProperty('include_inactive')
  })
})

// ---------------------------------------------------------------------------
// NEW: mapEvent createdBy nullable
// ---------------------------------------------------------------------------

describe('mapEvent createdBy nullable', () => {
  it('maps created_by null to null', () => {
    const ev = mapEvent(rawEv({ created_by: null }))
    expect(ev.createdBy).toBeNull()
  })

  it('maps absent created_by to null', () => {
    const raw: Record<string, unknown> = { id: 'x', title: 'T', start_at: 's', end_at: 'e', event_timezone: 'UTC', created_at: 'c', updated_at: 'u' }
    const ev = mapEvent(raw)
    expect(ev.createdBy).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// NEW: createCategory camelCase input
// ---------------------------------------------------------------------------

describe('calendarEventsApi.createCategory', () => {
  it('sends name, color and sort_order in snake_case from camelCase input', async () => {
    mockApi.post.mockResolvedValue({ data: rawCat() })
    await calendarEventsApi.createCategory({ name: 'Tax', color: '#0000FF', sortOrder: 5 })
    expect(mockApi.post).toHaveBeenCalledWith(
      '/api/v1/calendar/categories',
      { name: 'Tax', color: '#0000FF', sort_order: 5 }
    )
  })

  it('omits sort_order when sortOrder is undefined', async () => {
    mockApi.post.mockResolvedValue({ data: rawCat() })
    await calendarEventsApi.createCategory({ name: 'Tax', color: '#0000FF' })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).toHaveProperty('name', 'Tax')
    expect(body).toHaveProperty('color', '#0000FF')
    expect(body).not.toHaveProperty('sort_order')
  })
})

// ---------------------------------------------------------------------------
// NEW: createEvent camelCase input
// ---------------------------------------------------------------------------

describe('calendarEventsApi.createEvent', () => {
  it('sends title, start_at and end_at in snake_case from camelCase input', async () => {
    mockApi.post.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.createEvent({
      title: 'Review',
      startAt: '2026-10-15T14:00:00Z',
      endAt: '2026-10-15T15:00:00Z',
    })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).toHaveProperty('title', 'Review')
    expect(body).toHaveProperty('start_at', '2026-10-15T14:00:00Z')
    expect(body).toHaveProperty('end_at', '2026-10-15T15:00:00Z')
  })

  it('passes category_id null through when categoryId is null', async () => {
    mockApi.post.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.createEvent({
      title: 'Review',
      startAt: '2026-10-15T14:00:00Z',
      endAt: '2026-10-15T15:00:00Z',
      categoryId: null,
    })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).toHaveProperty('category_id', null)
  })

  it('omits owner_user_id when ownerUserId is undefined', async () => {
    mockApi.post.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.createEvent({
      title: 'Review',
      startAt: '2026-10-15T14:00:00Z',
      endAt: '2026-10-15T15:00:00Z',
    })
    const body = mockApi.post.mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('owner_user_id')
  })
})

// ---------------------------------------------------------------------------
// NEW: listEventsInRange offset assertions
// ---------------------------------------------------------------------------

describe('calendarEventsApi.listEventsInRange offset progression', () => {
  it('sends offsets 0, 100, 200 and limit 100 on each of the three calls', async () => {
    const makeItems = (count: number) =>
      Array.from({ length: count }, (_, i) => rawEv({ id: String(i) }))

    mockApi.get
      .mockResolvedValueOnce({ data: { items: makeItems(100), total: 230 } })
      .mockResolvedValueOnce({ data: { items: makeItems(100), total: 230 } })
      .mockResolvedValueOnce({ data: { items: makeItems(30), total: 230 } })

    await calendarEventsApi.listEventsInRange({ from: FROM, to: TO })

    const call0 = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    const call1 = mockApi.get.mock.calls[1][1]?.params as Record<string, unknown>
    const call2 = mockApi.get.mock.calls[2][1]?.params as Record<string, unknown>

    expect(call0).toMatchObject({ offset: 0, limit: 100 })
    expect(call1).toMatchObject({ offset: 100, limit: 100 })
    expect(call2).toMatchObject({ offset: 200, limit: 100 })
  })

  it('sends offsets 0 and 100 in the two calls before the empty page stops the loop', async () => {
    const makeItems = (count: number) =>
      Array.from({ length: count }, (_, i) => rawEv({ id: String(i) }))

    mockApi.get
      .mockResolvedValueOnce({ data: { items: makeItems(100), total: 500 } })
      .mockResolvedValueOnce({ data: { items: [], total: 500 } })

    await calendarEventsApi.listEventsInRange({ from: FROM, to: TO })

    const call0 = mockApi.get.mock.calls[0][1]?.params as Record<string, unknown>
    const call1 = mockApi.get.mock.calls[1][1]?.params as Record<string, unknown>

    expect(call0).toMatchObject({ offset: 0, limit: 100 })
    expect(call1).toMatchObject({ offset: 100, limit: 100 })
  })
})

// ---------------------------------------------------------------------------
// NEW: address tests (one per function)
// ---------------------------------------------------------------------------

describe('calendarEventsApi addresses', () => {
  it('listCategories calls GET /api/v1/calendar/categories', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listCategories()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/calendar/categories', expect.anything())
  })

  it('createCategory calls POST /api/v1/calendar/categories', async () => {
    mockApi.post.mockResolvedValue({ data: rawCat() })
    await calendarEventsApi.createCategory({ name: 'X', color: '#000' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/calendar/categories', expect.anything())
  })

  it('updateCategory calls PATCH /api/v1/calendar/categories/cat-1', async () => {
    mockApi.patch.mockResolvedValue({ data: rawCat() })
    await calendarEventsApi.updateCategory('cat-1', { name: 'Y' })
    expect(mockApi.patch).toHaveBeenCalledWith('/api/v1/calendar/categories/cat-1', expect.anything())
  })

  it('listEvents calls GET /api/v1/calendar/events', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listEvents({ from: FROM, to: TO })
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/calendar/events', expect.anything())
  })

  it('getEvent calls GET /api/v1/calendar/events/ev-1', async () => {
    mockApi.get.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.getEvent('ev-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/calendar/events/ev-1')
  })

  it('createEvent calls POST /api/v1/calendar/events', async () => {
    mockApi.post.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.createEvent({ title: 'X', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/calendar/events', expect.anything())
  })

  it('updateEvent calls PATCH /api/v1/calendar/events/ev-1', async () => {
    mockApi.patch.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.updateEvent('ev-1', { title: 'Y' })
    expect(mockApi.patch).toHaveBeenCalledWith('/api/v1/calendar/events/ev-1', expect.anything())
  })

  it('deleteEvent calls DELETE /api/v1/calendar/events/ev-1', async () => {
    mockApi.delete.mockResolvedValue({ status: 204, data: undefined })
    await calendarEventsApi.deleteEvent('ev-1')
    expect(mockApi.delete).toHaveBeenCalledWith('/api/v1/calendar/events/ev-1')
  })

  it('restoreEvent calls POST /api/v1/calendar/events/ev-1/restore', async () => {
    mockApi.post.mockResolvedValue({ data: rawEv() })
    await calendarEventsApi.restoreEvent('ev-1')
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/calendar/events/ev-1/restore')
  })

  it('listEventsInRange calls GET /api/v1/calendar/events', async () => {
    mockApi.get.mockResolvedValue({ data: { items: [], total: 0 } })
    await calendarEventsApi.listEventsInRange({ from: FROM, to: TO })
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/calendar/events', expect.anything())
  })
})