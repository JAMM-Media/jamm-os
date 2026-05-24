═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend changes only. Four files total.

═══════════════════════════════════════════════════════════════
TASK: Filters for Documents, Billing, Notifications, Timesheets
═══════════════════════════════════════════════════════════════

The select dropdown style used throughout is:
  className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border
  dark:border-dark-border bg-surface-card dark:bg-dark-card
  text-brand dark:text-[#EDEEF0] cursor-pointer"

Use this exact className on every new <select> element.

─────────────────────────────────────────────────────────────
FILE 1 — frontend/src/app/documents/page.tsx
─────────────────────────────────────────────────────────────

Add clientsApi to the existing import from '@/lib/api':
  BEFORE: import { documentsApi } from '@/lib/api'
  AFTER:  import { documentsApi, clientsApi } from '@/lib/api'

ADD two new state variables directly after
const [search, setSearch] = useState(''):

  const [clientFilter, setClientFilter] = useState<string>('all')
  const [engagementFilter, setEngagementFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')

ADD a clients fetch directly after the existing documents fetch:
  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])

After the documents const is defined, add:
  const uniqueEngagements = Array.from(
    new Set(documents.map((d) => d.engagementTitle).filter(Boolean))
  ).sort()

UPDATE the filtered const:
  BEFORE:
    const filtered = documents.filter((d) =>
      d.name.toLowerCase().includes(search.toLowerCase()) ||
      d.clientName.toLowerCase().includes(search.toLowerCase()) ||
      d.engagementTitle.toLowerCase().includes(search.toLowerCase())
    )

  AFTER:
    const filtered = documents.filter((d) => {
      if (
        search &&
        !d.name.toLowerCase().includes(search.toLowerCase()) &&
        !d.clientName.toLowerCase().includes(search.toLowerCase()) &&
        !d.engagementTitle.toLowerCase().includes(search.toLowerCase())
      ) return false
      if (clientFilter !== 'all' && d.clientId !== clientFilter) return false
      if (engagementFilter !== 'all' && d.engagementTitle !== engagementFilter) return false
      if (statusFilter !== 'all' && d.status !== statusFilter) return false
      return true
    })

ADD a filter bar div immediately after the closing </div> of
the toolbar div (the one containing search, ViewToggle, and
Upload Document button):

  <div className="flex items-center gap-2 flex-wrap">
    <select
      value={clientFilter}
      onChange={(e) => { setClientFilter(e.target.value); setEngagementFilter('all') }}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Clients</option>
      {(clientsData?.items ?? [])
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((c) => (
          <option key={c.id} value={c.id}>{c.name}</option>
        ))}
    </select>

    <select
      value={engagementFilter}
      onChange={(e) => setEngagementFilter(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Engagements</option>
      {uniqueEngagements.map((title) => (
        <option key={title} value={title}>{title}</option>
      ))}
    </select>

    <select
      value={statusFilter}
      onChange={(e) => setStatusFilter(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Statuses</option>
      <option value="uploaded">Uploaded</option>
      <option value="pending">Pending</option>
      <option value="pending_signature">Pending Signature</option>
      <option value="signed">Signed</option>
      <option value="rejected">Rejected</option>
    </select>

    {(clientFilter !== 'all' || engagementFilter !== 'all' || statusFilter !== 'all') && (
      <button
        onClick={() => { setClientFilter('all'); setEngagementFilter('all'); setStatusFilter('all') }}
        className="text-[11px] text-[#6B7280] hover:text-brand underline"
      >
        Clear filters
      </button>
    )}

    {(clientFilter !== 'all' || engagementFilter !== 'all' || statusFilter !== 'all') && (
      <span className="text-[11px] text-[#6B7280]">
        Showing {filtered.length} of {documents.length} documents
      </span>
    )}
  </div>

Update the empty state condition:
  BEFORE: } : filtered.length === 0 && search === '' ? (
  AFTER:  } : filtered.length === 0 && search === '' && clientFilter === 'all' && engagementFilter === 'all' && statusFilter === 'all' ? (

─────────────────────────────────────────────────────────────
FILE 2 — frontend/src/app/billing/page.tsx
─────────────────────────────────────────────────────────────

ADD three new state variables directly after
const [localInvoices, setLocalInvoices] = useState<Invoice[]>([]):

  const [clientFilter, setClientFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [dueDateSort, setDueDateSort] = useState<string>('asc')

UPDATE the filtered const:
  BEFORE:
    const filtered = invoices.filter((inv) => {
      const q = search.toLowerCase()
      const clientName = (clientMap[inv.clientId] ?? '').toLowerCase()
      return (
        inv.invoiceNumber.toLowerCase().includes(q) ||
        clientName.includes(q)
      )
    })

  AFTER:
    const filtered = invoices
      .filter((inv) => {
        const q = search.toLowerCase()
        const clientName = (clientMap[inv.clientId] ?? '').toLowerCase()
        if (q && !inv.invoiceNumber.toLowerCase().includes(q) && !clientName.includes(q)) return false
        if (clientFilter !== 'all' && inv.clientId !== clientFilter) return false
        if (statusFilter !== 'all' && inv.status !== statusFilter) return false
        return true
      })
      .sort((a, b) => {
        const aDate = a.dueDate ? new Date(a.dueDate).getTime() : Infinity
        const bDate = b.dueDate ? new Date(b.dueDate).getTime() : Infinity
        return dueDateSort === 'asc' ? aDate - bDate : bDate - aDate
      })

ADD a filter bar div immediately after the closing </div> of
the toolbar div (the one containing search, ViewToggle, and
+ New Invoice button):

  <div className="flex items-center gap-2 flex-wrap">
    <select
      value={clientFilter}
      onChange={(e) => setClientFilter(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Clients</option>
      {(clientsData?.items ?? [])
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((c) => (
          <option key={c.id} value={c.id}>{c.name}</option>
        ))}
    </select>

    <select
      value={statusFilter}
      onChange={(e) => setStatusFilter(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Statuses</option>
      <option value="draft">Draft</option>
      <option value="sent">Sent</option>
      <option value="paid">Paid</option>
      <option value="overdue">Overdue</option>
      <option value="void">Void</option>
    </select>

    <select
      value={dueDateSort}
      onChange={(e) => setDueDateSort(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="asc">Due Date ↑ Earliest</option>
      <option value="desc">Due Date ↓ Latest</option>
    </select>

    {(clientFilter !== 'all' || statusFilter !== 'all') && (
      <button
        onClick={() => { setClientFilter('all'); setStatusFilter('all'); setDueDateSort('asc') }}
        className="text-[11px] text-[#6B7280] hover:text-brand underline"
      >
        Clear filters
      </button>
    )}

    {(clientFilter !== 'all' || statusFilter !== 'all') && (
      <span className="text-[11px] text-[#6B7280]">
        Showing {filtered.length} of {invoices.length} invoices
      </span>
    )}
  </div>

Update the empty state condition:
  BEFORE: } : filtered.length === 0 && search === '' ? (
  AFTER:  } : filtered.length === 0 && search === '' && clientFilter === 'all' && statusFilter === 'all' ? (

─────────────────────────────────────────────────────────────
FILE 3 — frontend/src/app/notifications/page.tsx
─────────────────────────────────────────────────────────────

The type filter dropdown currently uses dynamically generated
raw backend strings as option labels. Replace it with a
hardcoded label map approach.

REMOVE this line entirely:
  const uniqueTypes = Array.from(new Set(notifications.map((n) => n.notification_type)))

ADD this constant before the return statement:
  const NOTIFICATION_TYPE_LABELS: Record<string, string> = {
    'mention': '@ Mention',
    'task.assigned': 'Task Assigned',
    'task.completed': 'Task Completed',
    'task.overdue': 'Task Overdue',
    'engagement.deadline_approaching': 'Deadline Approaching',
    'engagement.completed': 'Engagement Completed',
    'document_request.completed': 'Documents Received',
    'document_request.reminder_sent': 'Document Reminder Sent',
    'invoice.paid': 'Invoice Paid',
    'invoice.overdue': 'Invoice Overdue',
    'invoice.reminder_sent': 'Invoice Reminder Sent',
    'irs_authorization.expiry_approaching': 'IRS Auth Expiring',
    'portal.first_login': 'Client Portal Login',
    'firm_chat.message': 'Firm Chat Message',
    'anniversary': 'Client Anniversary',
    'automation.fired': 'Automation Fired',
  }

ADD this derived list after the NOTIFICATION_TYPE_LABELS const:
  const uniqueTypes = Array.from(
    new Set(notifications.map((n) => n.notification_type))
  ).sort()

FIND the existing type filter select and replace its option
list:
  BEFORE:
    <option value="all">All Types</option>
    {uniqueTypes.map((t) => <option key={t} value={t}>{t}</option>)}

  AFTER:
    <option value="all">All Types</option>
    {uniqueTypes.map((t) => (
      <option key={t} value={t}>
        {NOTIFICATION_TYPE_LABELS[t] ?? t}
      </option>
    ))}

This keeps the dynamic approach so only types that actually
exist in the data appear — but shows clean labels instead of
raw strings. Unknown types fall back to the raw string.

─────────────────────────────────────────────────────────────
FILE 4 — frontend/src/app/(dashboard)/timesheets/page.tsx
─────────────────────────────────────────────────────────────

ADD one new state variable directly after the existing
const [selectedUserId, setSelectedUserId] = useState<string | null>(null) line:

  const [billableFilter, setBillableFilter] = useState<string>('all')

Pass the new prop down to every tab component. Each tab
currently receives selectedUserId, currentUserId, and userRole.
Add billableFilter to all six tab usages:

  BEFORE (example for DailyTab — apply same change to all 6):
    <DailyTab
      selectedUserId={selectedUserId}
      currentUserId={user.id}
      userRole={user.role}
    />

  AFTER:
    <DailyTab
      selectedUserId={selectedUserId}
      currentUserId={user.id}
      userRole={user.role}
      billableFilter={billableFilter}
    />

Apply the same billableFilter prop addition to WeeklyTab,
BiweeklyTab, MonthlyTab, QuarterlyTab, and YearlyTab.

ADD the billable filter select to the page header row,
immediately after the existing staff select dropdown.
The header row currently has the staff select on the right.
Add the billable select next to it:

  <select
    value={billableFilter}
    onChange={(e) => setBillableFilter(e.target.value)}
    className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none"
  >
    <option value="all">All Entries</option>
    <option value="billable">Billable Only</option>
    <option value="non_billable">Non-Billable Only</option>
  </select>

NOTE: The billableFilter select should always be visible,
not gated behind isManagerOrAbove — all users benefit from
filtering by billable status on their own entries.

Now update the tab component files to accept and use the
new prop.

FILE 4A — DailyTab.tsx
Add billableFilter to the DailyTabProps interface:
  BEFORE:
    export interface DailyTabProps {
      selectedUserId: string | null
      currentUserId: string
      userRole: string
    }
  AFTER:
    export interface DailyTabProps {
      selectedUserId: string | null
      currentUserId: string
      userRole: string
      billableFilter?: string
    }

Find where DailyTab renders its list of time entries and add
a filter. The entries are stored in a local state array —
find where they are mapped for display and add a filter before
the map:

  Filter the entries array before rendering:
  entries.filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    return true
  }).map(...)

FILE 4B — AggregateTab.tsx
Add billableFilter to the AggregateTabProps interface:
  BEFORE:
    export interface AggregateTabProps {
      period: Period
      selectedUserId: string | null
      currentUserId: string
      userRole: string
    }
  AFTER:
    export interface AggregateTabProps {
      period: Period
      selectedUserId: string | null
      currentUserId: string
      userRole: string
      billableFilter?: string
    }

AggregateTab shows summary rows with billable_hours and
billable_pct columns. The billable filter here should filter
the summary rows by whether they have any billable hours:

  Filter summaryRows before rendering:
  summaryRows.filter((row) => {
    if (billableFilter === 'billable') return row.billable_hours > 0
    if (billableFilter === 'non_billable') return row.billable_hours === 0
    return true
  }).map(...)

BiweeklyTab, WeeklyTab, MonthlyTab, QuarterlyTab, YearlyTab
all use AggregateTab. Their Props type is
Omit<AggregateTabProps, 'period'> which automatically
includes billableFilter once it is added to AggregateTabProps.
No changes needed in those files.

─────────────────────────────────────────────────────────────
AFTER ALL FILES
─────────────────────────────────────────────────────────────
Report every file modified and the exact lines changed.
Do not run any backend or alembic commands.