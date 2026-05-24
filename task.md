═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend changes only. Two files total.

═══════════════════════════════════════════════════════════════
TASK: Add engagement filter to Timesheets + fix API path bug
═══════════════════════════════════════════════════════════════

─────────────────────────────────────────────────────────────
FILE 1 — frontend/src/app/(dashboard)/timesheets/page.tsx
─────────────────────────────────────────────────────────────

ADD one new state variable directly after:
  const [billableFilter, setBillableFilter] = useState<string>('all')

Add:
  const [engagementFilter, setEngagementFilter] = useState<string>('all')

Pass the new prop down to all six tab components.
Each tab currently receives billableFilter. Add engagementFilter
to all six:

  BEFORE (apply to all 6 tabs):
    billableFilter={billableFilter}
  AFTER:
    billableFilter={billableFilter}
    engagementFilter={engagementFilter}

ADD an engagement select to the header row div, after the
billable filter select and before the staff select.

The page does not have an engagements list yet. Add a fetch
directly after the staffList useEffect block, inside the
component before the return statement:

  const [engagementList, setEngagementList] = useState<{ id: string; name: string }[]>([])

  useEffect(() => {
    api.get('/engagements/?limit=100').then((r) => {
      const items = r.data?.items ?? []
      setEngagementList(items.map((e: { id: string; name: string }) => ({ id: e.id, name: e.name })))
    }).catch(() => {})
  }, [])

NOTE: Use '/engagements/?limit=100' NOT '/api/v1/engagements/'
— the axios baseURL already includes /api/backend so the
/api/v1/ prefix is wrong and causes a 404.

Add the engagement select to the header row div, in the same
flex container as the billable and staff selects:

  <select
    value={engagementFilter}
    onChange={(e) => setEngagementFilter(e.target.value)}
    className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none"
  >
    <option value="all">All Engagements</option>
    {engagementList
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((e) => (
        <option key={e.id} value={e.id}>{e.name}</option>
      ))}
  </select>

─────────────────────────────────────────────────────────────
FILE 2 — frontend/src/app/(dashboard)/timesheets/AggregateTab.tsx
─────────────────────────────────────────────────────────────

STEP 1 — Fix the wrong API path for the engagements fetch.

Find:
  api.get('/api/v1/engagements/?limit=100')

Replace with:
  api.get('/engagements/?limit=100')

STEP 2 — Add engagementFilter to AggregateTabProps interface.

BEFORE:
  export interface AggregateTabProps {
    period: Period
    selectedUserId: string | null
    currentUserId: string
    userRole: string
    billableFilter?: string
  }

AFTER:
  export interface AggregateTabProps {
    period: Period
    selectedUserId: string | null
    currentUserId: string
    userRole: string
    billableFilter?: string
    engagementFilter?: string
  }

STEP 3 — Destructure engagementFilter from props.

Find the existing destructure:
  billableFilter = 'all',
}: AggregateTabProps)

Add engagementFilter after it:
  billableFilter = 'all',
  engagementFilter = 'all',
}: AggregateTabProps)

STEP 4 — Apply engagementFilter to the summaryRows filter.

Find the existing summaryRows filter:
  const summaryRows = summary.filter((row) => {
    if (billableFilter === 'billable') return row.billable_hours > 0
    if (billableFilter === 'non_billable') return row.billable_hours === 0
    return true
  })

The SummaryRow type does not have an engagement_id field —
summary rows are grouped by user, not engagement. So the
engagement filter applies to the entries detail table only,
not the summary rows. Leave summaryRows filter unchanged.

STEP 5 — Apply engagementFilter to the entries detail table.

Find the existing entries filter before the detail table map:
  {entries.filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    return true
  }).map((entry, i) => {

Add the engagement check inside that filter:
  {entries.filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    if (engagementFilter !== 'all' && e.engagement_id !== engagementFilter) return false
    return true
  }).map((entry, i) => {

─────────────────────────────────────────────────────────────
FILE 3 — frontend/src/app/(dashboard)/timesheets/DailyTab.tsx
─────────────────────────────────────────────────────────────

STEP 1 — Add engagementFilter to DailyTabProps interface.

BEFORE:
  export interface DailyTabProps {
    selectedUserId: string | null
    currentUserId: string
    userRole: string
    billableFilter?: string
  }

AFTER:
  export interface DailyTabProps {
    selectedUserId: string | null
    currentUserId: string
    userRole: string
    billableFilter?: string
    engagementFilter?: string
  }

STEP 2 — Destructure engagementFilter from props.

Find:
  export default function DailyTab({ selectedUserId, currentUserId, userRole, billableFilter = 'all' }: DailyTabProps)

Replace with:
  export default function DailyTab({ selectedUserId, currentUserId, userRole, billableFilter = 'all', engagementFilter = 'all' }: DailyTabProps)

STEP 3 — Apply engagementFilter to both pending and submitted
filters.

Find the existing pending filter:
  const pending = entries.filter((e) => !e.is_submitted).filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    return true
  })

Replace with:
  const pending = entries.filter((e) => !e.is_submitted).filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    if (engagementFilter !== 'all' && e.engagement_id !== engagementFilter) return false
    return true
  })

Find the existing submitted filter:
  const submitted = entries.filter((e) => e.is_submitted).filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    return true
  })

Replace with:
  const submitted = entries.filter((e) => e.is_submitted).filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    if (engagementFilter !== 'all' && e.engagement_id !== engagementFilter) return false
    return true
  })

─────────────────────────────────────────────────────────────
AFTER ALL FILES
─────────────────────────────────────────────────────────────
Report every file modified and the exact lines changed.
Do not run any backend or alembic commands.