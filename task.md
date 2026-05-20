# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed. Do not skip steps or reorder them.

---

## STANDING RULES

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0, Pydantic v2. Never deviate from existing patterns.
- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.
- Domain language: Engagement not Project. Staff not Employee. Firm not Company. Client not Customer.

---

## TASK 1 — Extend JWT and refresh token lifetimes

**Files to edit:**
- `app/services/staff_refresh_service.py`
- `app/core/config.py`

In `app/services/staff_refresh_service.py`, find the two constants near the top and update them:
```python
REFRESH_INACTIVITY_HOURS = 8     # was 2
REFRESH_ABSOLUTE_HOURS = 72      # was 12
```

In `app/core/config.py`, find `ACCESS_TOKEN_EXPIRE_MINUTES` and update it:
```python
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60   # was 30
```

No migration required. No frontend changes required.

---

## TASK 2 — Dashboard overdue count updates live when engagement marked complete

**File to edit:** `frontend/src/app/dashboard/page.tsx`

**Problem:** The stat card at the top reads `metrics?.overdue_engagement_count` directly from the server response. When a row is marked complete and dismissed via `dismissedIds`, the table disappears but the number doesn't change because it still points to the stale server value. `visibleOverdue` is already computed correctly by filtering out dismissed IDs — the stat card just isn't reading from it.

**Fix:** Find the StatCard that renders the overdue engagement count. It currently uses something like:
```tsx
value={String(metrics?.overdue_engagement_count)}
```
Change it to:
```tsx
value={String(visibleOverdue.length)}
```

If there is a subtitle or description line near that StatCard that also references `overdue_engagement_count`, update it to use `visibleOverdue.length` as well.

That is the only change needed in this task.

---

## TASK 3 — @mention styling: remove highlight chip, use bold text instead

This change applies to **two separate components**: the firm chat and the notes panel. The rule is the same in both: `@Name` renders as bold text, no background color, no chip.

### 3A — Firm Chat

**File to edit:** `frontend/src/components/firm-chat/FirmChatPage.tsx` (search for the `renderBody` function)

Inside `renderBody`, there are two `<span>` elements that render the highlighted mention — one in the `sortedNames.length === 0` fallback branch and one in the main branch. Both currently look like:
```tsx
<span key={match.index} className="bg-status-blue text-status-blue-text rounded px-1 font-medium">
  {match[0]}
</span>
```

Replace both with:
```tsx
<span key={match.index} className="font-semibold">
  {match[0]}
</span>
```

No other changes to this function.

### 3B — Notes Panel

**File to edit:** `frontend/src/components/notes/NotesPanel.tsx`

The `NoteCard` component currently renders `note.body` as a plain text paragraph:
```tsx
<p className="text-[13px] text-[#374151] dark:text-[#9CA3AF] leading-[1.6]">
  {note.body}
</p>
```

Replace this with a `renderNoteBody` helper that bolds `@Name` mentions the same way as firm chat. Add this helper function above the `NoteCard` component definition:

```tsx
function renderNoteBody(body: string): React.ReactNode {
  if (!body) return <>{body}</>
  const parts: React.ReactNode[] = []
  const regex = /@(\S+(?:\s\S+)?)/g
  let last = 0
  let match
  let found = false
  while ((match = regex.exec(body)) !== null) {
    found = true
    if (match.index > last) parts.push(<span key={last}>{body.slice(last, match.index)}</span>)
    parts.push(
      <span key={match.index} className="font-semibold">
        {match[0]}
      </span>
    )
    last = match.index + match[0].length
  }
  if (last < body.length) parts.push(<span key={last}>{body.slice(last)}</span>)
  return found ? <>{parts}</> : <>{body}</>
}
```

Then update the paragraph inside `NoteCard` to use it:
```tsx
<p className="text-[13px] text-[#374151] dark:text-[#9CA3AF] leading-[1.6]">
  {renderNoteBody(note.body)}
</p>
```

No other changes to this file.

---

## TASK 4 — Task auto-status live update for managers and firm owners

**File to edit:** `frontend/src/app/tasks/[id]/page.tsx`

The existing `useEffect` that auto-sets a task from `todo` to `in_progress` when the assignee opens it is correct and should not be changed. The issue is that other users (managers, firm owners) viewing the same task won't see that status change in real time.

Add a polling `useEffect` immediately after the existing auto-status `useEffect`:

```tsx
// Poll so managers/owners see the in_progress transition without manual reload
useEffect(() => {
  if (!task || task.status === 'completed' || task.status === 'done') return
  const interval = setInterval(() => {
    refetch()
  }, 10000)
  return () => clearInterval(interval)
}, [task?.status, refetch])
```

This polls every 10 seconds when the task is in an active state, stopping once it reaches a terminal status. Do not remove or modify the existing auto-status `useEffect`.

---

## TASK 5 — Hide Dashboard nav item from staff role

**File to edit:** `frontend/src/components/layout/AppShell.tsx` (search for `const navItems`)

The `Sidebar` component already uses `useAuth`. Add a `visibleNavItems` constant that filters out the Dashboard link for staff users, then use it in place of `navItems` in the map call.

Add this immediately before the `navItems.map(...)` call:
```tsx
const visibleNavItems = navItems.filter((item) => {
  if (item.href === '/dashboard' && user?.role === 'staff') return false
  return true
})
```

Then change `navItems.map(...)` to `visibleNavItems.map(...)`.

Check whether `user` is already destructured from `useAuth` in this component. If it is, do not call `useAuth` again — just add the `visibleNavItems` constant using the existing `user` variable.

---

## TASK 6 — Fix engagement "active" status badge color to blue

**File to edit:** `frontend/src/components/ui/StatusBadge.tsx`

Find the `active` entry in `variantConfig`:
```ts
active: {
  bg: 'bg-status-green',
  text: 'text-status-green-text',
  defaultLabel: 'Active',
},
```

Change it to:
```ts
active: {
  bg: 'bg-status-blue',
  text: 'text-status-blue-text',
  defaultLabel: 'Active',
},
```

No other changes to this file.

---

## TASK 7 — Wire the "Send Reminder" button for awaiting-signature documents on the dashboard

### 7A — Backend: add esign reminder method and endpoint

**File to edit first:** `app/services/dropbox_sign.py`

Add this function at the bottom of the file:
```python
def send_reminder(signature_request_id: str, signer_email: str | None = None) -> dict:
    """
    Sends a reminder for an existing Dropbox Sign signature request.
    Raises HTTPException(502) if the upstream call fails.
    """
    data = {}
    if signer_email:
        data["email_address"] = signer_email

    r = requests.post(
        f"{_BASE_URL}/signature_request/remind/{signature_request_id}",
        auth=_get_auth(),
        data=data,
        timeout=30,
    )

    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Dropbox Sign reminder failed: {r.status_code} — {r.text}",
        )

    return r.json()
```

**File to edit second:** `app/api/esign.py`

Add this endpoint after the existing `/send` endpoint. Check the imports at the top of `esign.py` — `datetime`, `timezone`, and `SignatureEnvelopeUpdate` should already be imported. Add only what is missing.

```python
@router.post("/envelopes/{envelope_id}/remind")
def send_envelope_reminder(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    if envelope.status != "sent":
        raise HTTPException(status_code=400, detail="Reminders can only be sent for envelopes with status 'sent'")
    if not envelope.provider_envelope_id:
        raise HTTPException(status_code=400, detail="Envelope has no provider ID")

    dropbox_sign.send_reminder(
        signature_request_id=envelope.provider_envelope_id,
        signer_email=envelope.signers[0]["email"] if envelope.signers else None,
    )

    now = datetime.now(timezone.utc)
    crud_envelope.update_signature_envelope(
        db,
        envelope,
        SignatureEnvelopeUpdate(
            reminder_count=(envelope.reminder_count or 0) + 1,
            last_reminder_sent_at=now,
        ),
    )

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="esign.reminder_sent",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope_id,
    )

    return {"sent": True, "reminder_count": (envelope.reminder_count or 0) + 1}
```

### 7B — Frontend: wire the Send Reminder button

**File to edit:** `frontend/src/app/dashboard/page.tsx`

Find the `UnsignedDocumentsTable` component. The Send Reminder action cell currently renders a dead `<span>` with `cursor-not-allowed` and title "Coming soon".

Add `useState` to the component (it currently has none) and replace the action cell:

```tsx
function UnsignedDocumentsTable({ items }: { items: UnsignedDocumentItem[] }) {
  const [sending, setSending] = useState<string | null>(null)

  async function handleRemind(envelopeId: string) {
    setSending(envelopeId)
    try {
      await api.post(`/esign/envelopes/${envelopeId}/remind`)
      toast.success('Reminder sent')
    } catch {
      toast.error('Failed to send reminder')
    } finally {
      setSending(null)
    }
  }

  // ... keep all existing JSX exactly as-is, only replace the action <td>:
```

Replace the action `<td>` from:
```tsx
<td className="px-4 py-2.5">
  <span
    title="Coming soon"
    className="inline-block text-[11px] font-medium px-2.5 py-1 rounded border border-surface-border dark:border-dark-border text-[#9CA3AF] cursor-not-allowed select-none"
  >
    Send Reminder
  </span>
</td>
```

To:
```tsx
<td className="px-4 py-2.5">
  <button
    onClick={() => handleRemind(item.envelope_id)}
    disabled={sending === item.envelope_id}
    className="text-[11px] font-medium px-2.5 py-1 rounded border border-surface-border dark:border-dark-border text-brand dark:text-[#EDEEF0] hover:bg-surface-card dark:hover:bg-dark-card disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
  >
    {sending === item.envelope_id ? 'Sending...' : 'Send Reminder'}
  </button>
</td>
```

Keep all other JSX in the component identical.

---

## TASK 8 — Filters and sorting on Engagements and Tasks pages

All filtering is client-side — the pages already fetch up to 100 records in one call. Filters apply to the already-loaded array using JavaScript. No new API calls are needed.

### 8A — Engagements page

**File to edit:** `frontend/src/app/engagements/page.tsx`

**Add filter state** (add alongside existing `useState` declarations):
```tsx
const [statusFilter, setStatusFilter] = useState<string>('all')
const [typeFilter, setTypeFilter] = useState<string>('all')
```

**Update the `filtered` computation** (replace the existing one):
```tsx
const uniqueTypes = Array.from(new Set(engagements.map((e) => e.engagement_type).filter(Boolean)))

const filtered = engagements.filter((e) => {
  if (search && !e.name.toLowerCase().includes(search.toLowerCase())) return false
  if (statusFilter !== 'all' && e.status !== statusFilter) return false
  if (typeFilter !== 'all' && e.engagement_type !== typeFilter) return false
  return true
})
```

**Add filter UI** directly below the existing toolbar row (search bar + view toggle + new button). The filter bar is a flex row with a small left-aligned gap:

```tsx
{/* Filter bar */}
<div className="flex items-center gap-2 flex-wrap">
  <select
    value={statusFilter}
    onChange={(e) => setStatusFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Statuses</option>
    <option value="planning">Planning</option>
    <option value="active">Active</option>
    <option value="in_review">In Review</option>
    <option value="completed">Completed</option>
    <option value="archived">Archived</option>
  </select>

  <select
    value={typeFilter}
    onChange={(e) => setTypeFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Types</option>
    {uniqueTypes.map((t) => (
      <option key={t} value={t}>{t}</option>
    ))}
  </select>

  {(statusFilter !== 'all' || typeFilter !== 'all') && (
    <button
      onClick={() => { setStatusFilter('all'); setTypeFilter('all') }}
      className="text-[11px] text-[#6B7280] hover:text-brand underline"
    >
      Clear filters
    </button>
  )}

  {(statusFilter !== 'all' || typeFilter !== 'all') && (
    <span className="text-[11px] text-[#6B7280]">
      Showing {filtered.length} of {engagements.length} engagements
    </span>
  )}
</div>
```

### 8B — Tasks page

**File to edit:** `frontend/src/app/tasks/page.tsx`

**Add filter state:**
```tsx
const [statusFilter, setStatusFilter] = useState<string>('all')
const [myTasksOnly, setMyTasksOnly] = useState(false)
```

**Update filtered/sorted computation.** Find the existing filter logic and replace it with:
```tsx
const filtered = tasks
  .filter((t) => {
    if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter !== 'all' && t.status !== statusFilter) return false
    if (myTasksOnly && t.assigned_to !== user?.id) return false
    return true
  })
  .sort((a, b) => {
    // When not filtering to my tasks, sort user's own tasks to the top
    if (!myTasksOnly) {
      const aMe = a.assigned_to === user?.id ? 0 : 1
      const bMe = b.assigned_to === user?.id ? 0 : 1
      return aMe - bMe
    }
    return 0
  })
```

**Add filter UI** below the existing toolbar row:
```tsx
{/* Filter bar */}
<div className="flex items-center gap-2 flex-wrap">
  <select
    value={statusFilter}
    onChange={(e) => setStatusFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Statuses</option>
    <option value="todo">To Do</option>
    <option value="in_progress">In Progress</option>
    <option value="in_review">In Review</option>
    <option value="done">Done</option>
  </select>

  <button
    onClick={() => setMyTasksOnly((prev) => !prev)}
    className={`text-[12px] h-8 px-3 rounded-[6px] border font-medium transition-colors ${
      myTasksOnly
        ? 'bg-brand text-white border-brand'
        : 'border-surface-border dark:border-dark-border text-[#6B7280] dark:text-[#9CA3AF] bg-surface-card dark:bg-dark-card hover:text-brand'
    }`}
  >
    My Tasks
  </button>

  {(statusFilter !== 'all' || myTasksOnly) && (
    <button
      onClick={() => { setStatusFilter('all'); setMyTasksOnly(false) }}
      className="text-[11px] text-[#6B7280] hover:text-brand underline"
    >
      Clear filters
    </button>
  )}

  {(statusFilter !== 'all' || myTasksOnly) && (
    <span className="text-[11px] text-[#6B7280]">
      Showing {filtered.length} of {tasks.length} tasks
    </span>
  )}
</div>
```

Make sure `user` is available in this component — it should already be via `useAuth`. If not, add `const { user } = useAuth()`.

---

## TASK 9 — Notifications page

### 9A — Frontend: create notifications page

**File to create:** `frontend/src/app/notifications/page.tsx`

Build a full notifications page at `/notifications` using `AppShell`. All data comes from existing backend endpoints — no backend changes needed.

**Endpoints to use:**
- `GET /api/v1/notifications/?limit=50` — list notifications
- `PATCH /api/v1/notifications/{id}` with `{ is_read: true }` — mark one read
- `PATCH /api/v1/notifications/read-all` — mark all read

**Page structure:**

```tsx
'use client'

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { api } from '@/lib/api'
import { toast } from 'sonner'

// Notification type from backend NotificationOut schema
interface Notification {
  id: string
  title: string
  body: string
  notification_type: string
  is_read: boolean
  created_at: string
  related_entity_type?: string
  related_entity_id?: string
}

// Relative timestamp helper
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'Yesterday'
  return `${days}d ago`
}

// Entity navigation map
function getEntityPath(type?: string, id?: string): string | null {
  if (!type || !id) return null
  const map: Record<string, string> = {
    engagement: `/engagements/${id}`,
    task: `/tasks/${id}`,
    client: `/clients/${id}`,
    message: '/firm-chat',
  }
  return map[type] ?? null
}

export default function NotificationsPage() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [readFilter, setReadFilter] = useState('all')

  const { data, isLoading, isError, refetch } = useQuery<{ items: Notification[] }>({
    queryKey: ['notifications'],
    queryFn: () => api.get('/api/v1/notifications/?limit=50').then((r) => r.data),
    staleTime: 30 * 1000,
  })

  const notifications = data?.items ?? []
  const unreadCount = notifications.filter((n) => !n.is_read).length

  const filtered = notifications.filter((n) => {
    if (search && !n.title.toLowerCase().includes(search.toLowerCase()) && !n.body.toLowerCase().includes(search.toLowerCase())) return false
    if (typeFilter !== 'all' && n.notification_type !== typeFilter) return false
    if (readFilter === 'unread' && n.is_read) return false
    if (readFilter === 'read' && !n.is_read) return false
    return true
  })

  async function handleMarkRead(id: string) {
    await api.patch(`/api/v1/notifications/${id}`, { is_read: true })
    queryClient.setQueryData(['notifications'], (old: { items: Notification[] } | undefined) => {
      if (!old) return old
      return { ...old, items: old.items.map((n) => n.id === id ? { ...n, is_read: true } : n) }
    })
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
  }

  async function handleMarkAllRead() {
    await api.patch('/api/v1/notifications/read-all')
    refetch()
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    toast.success('All notifications marked as read')
  }

  async function handleRowClick(n: Notification) {
    if (!n.is_read) await handleMarkRead(n.id)
    const path = getEntityPath(n.related_entity_type, n.related_entity_id)
    if (path) router.push(path)
  }

  // Unique notification types for the type filter dropdown
  const uniqueTypes = Array.from(new Set(notifications.map((n) => n.notification_type)))

  return (
    <AppShell>
      <div className="p-6 max-w-3xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h1 className="text-[24px] font-medium text-brand dark:text-[#EDEEF0]">Notifications</h1>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="text-[12px] font-medium text-[#6B7280] hover:text-brand underline"
            >
              Mark all as read
            </button>
          )}
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search notifications..."
            className="w-full h-9 pl-8 pr-3 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
          />
          <svg className="absolute left-2.5 top-2.5 w-4 h-4 text-[#9CA3AF]" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Types</option>
            {uniqueTypes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>

          <select
            value={readFilter}
            onChange={(e) => setReadFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All</option>
            <option value="unread">Unread</option>
            <option value="read">Read</option>
          </select>

          {(typeFilter !== 'all' || readFilter !== 'all') && (
            <button
              onClick={() => { setTypeFilter('all'); setReadFilter('all') }}
              className="text-[11px] text-[#6B7280] hover:text-brand underline"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Notification list */}
        {isLoading ? (
          <div className="space-y-2">
            {[1,2,3,4].map((i) => (
              <div key={i} className="h-16 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-12">
            <p className="text-[13px] text-[#6B7280] mb-3">Failed to load notifications.</p>
            <button onClick={() => refetch()} className="text-[12px] font-medium px-4 py-2 rounded-[6px] bg-brand text-white">Retry</button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2.5">
            <div className="w-10 h-10 rounded-[8px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card flex items-center justify-center">
              <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" className="text-[#6B7280]">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
              </svg>
            </div>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No notifications yet</p>
            <p className="text-[12px] text-[#6B7280]">You'll see mentions, messages, and updates here.</p>
          </div>
        ) : (
          <div className="space-y-1">
            {filtered.map((n) => {
              const hasLink = !!getEntityPath(n.related_entity_type, n.related_entity_id)
              return (
                <div
                  key={n.id}
                  onClick={() => handleRowClick(n)}
                  className={`flex items-start gap-3 px-4 py-3 rounded-[8px] transition-colors ${
                    n.is_read
                      ? 'bg-surface-card dark:bg-dark-card'
                      : 'bg-[#EDEEF0] dark:bg-[#2D2D2D] border border-surface-border dark:border-dark-border'
                  } ${hasLink ? 'cursor-pointer hover:bg-[#E4E6EA] dark:hover:bg-[#383838]' : ''}`}
                >
                  {/* Unread dot */}
                  <div className="flex-shrink-0 mt-1.5">
                    <div className={`w-2 h-2 rounded-full ${n.is_read ? 'bg-transparent' : 'bg-brand'}`} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] leading-snug">{n.title}</p>
                    <p className="text-[12px] text-[#6B7280] mt-0.5 truncate">{n.body}</p>
                  </div>

                  {/* Timestamp */}
                  <span className="text-[11px] text-[#6B7280] flex-shrink-0 mt-0.5">{relativeTime(n.created_at)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </AppShell>
  )
}
```

### 9B — Add Notifications link to sidebar with unread badge

**File to edit:** `frontend/src/components/layout/AppShell.tsx`

**Step 1:** Check whether `Bell` is already imported from `lucide-react`. If not, add it to the existing lucide-react import line.

**Step 2:** Add to `navItems` after the `Firm Chat` entry:
```tsx
{ href: '/notifications', label: 'Notifications', icon: Bell },
```

**Step 3:** In the `Sidebar` component body, add a query for the unread notification count. Import `useQuery` and `api` if not already imported in this file. Add:
```tsx
const { data: notifData } = useQuery({
  queryKey: ['notifications-unread-count'],
  queryFn: () => api.get('/api/v1/notifications/unread-count').then((r) => r.data),
  staleTime: 30 * 1000,
  refetchInterval: 60 * 1000,
})
const notifUnread: number = notifData?.count ?? 0
```

**Step 4:** In the `navItems.map(...)` (now `visibleNavItems.map(...)` after Task 5), add badge logic for the Notifications item using the same pattern already in place for Firm Chat's `totalUnread`. The relevant variables to check per item:
```tsx
const isNotifications = item.href === '/notifications'
const showNotifBadge = isNotifications && notifUnread > 0
const badgeCount = isNotifications ? notifUnread : totalUnread
const showBadge = (isFirmChat && totalUnread > 0) || showNotifBadge
```

Apply the collapsed badge (circle on icon) and expanded badge (pill right of label) using `badgeCount` when `showBadge` is true. Follow the exact same JSX pattern already used for the Firm Chat badge — do not invent a new pattern.

---

## EXECUTION ORDER

1. Task 1 — backend config only
2. Task 2 — frontend dashboard
3. Task 3A — firm chat mention styling
4. Task 3B — notes panel mention styling
5. Task 4 — task polling
6. Task 5 — hide dashboard from staff sidebar
7. Task 6 — active badge color
8. Task 7A — backend: dropbox_sign.py then esign.py
9. Task 7B — frontend: dashboard reminder button
10. Task 8A — engagements filters
11. Task 8B — tasks filters
12. Task 9A — create notifications page
13. Task 9B — add notifications to sidebar

After all tasks: report every file modified and confirm no TypeScript errors.
