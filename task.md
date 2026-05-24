═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend change only. One file.

═══════════════════════════════════════════════════════════════
TASK: Add engagement filter to Billing page
═══════════════════════════════════════════════════════════════

File: frontend/src/app/billing/page.tsx

─────────────────────────────────────────────────────────────
STEP 1 — Add engagementsApi to imports
─────────────────────────────────────────────────────────────

BEFORE: import { invoicesApi, clientsApi } from '@/lib/api'
AFTER:  import { invoicesApi, clientsApi, engagementsApi } from '@/lib/api'

─────────────────────────────────────────────────────────────
STEP 2 — Add engagementFilter state
─────────────────────────────────────────────────────────────

Directly after:
  const [clientFilter, setClientFilter] = useState<string>('all')

Add:
  const [engagementFilter, setEngagementFilter] = useState<string>('all')

─────────────────────────────────────────────────────────────
STEP 3 — Add engagements fetch
─────────────────────────────────────────────────────────────

Directly after the existing clientsData fetch line:
  const { data: clientsData, isLoading: clientsLoading } = useFetch(() => clientsApi.list(0, 100), [])

Add:
  const { data: engagementsData } = useFetch(() => engagementsApi.list(0, 100), [])

─────────────────────────────────────────────────────────────
STEP 4 — Build engagement map and unique engagements list
─────────────────────────────────────────────────────────────

Directly after the existing clientMap const, add:

  const engagementMap: Record<string, string> = Object.fromEntries(
    (engagementsData?.items ?? []).map((e) => [e.id, e.name])
  )

  const uniqueEngagementIds = Array.from(
    new Set(invoices.map((inv) => inv.engagementId).filter(Boolean))
  ) as string[]

─────────────────────────────────────────────────────────────
STEP 5 — Add engagementFilter to the filtered const
─────────────────────────────────────────────────────────────

Find the existing filter inside the .filter() call:
  if (statusFilter !== 'all' && inv.status !== statusFilter) return false
  return true

Add the engagement check before return true:
  if (engagementFilter !== 'all' && inv.engagementId !== engagementFilter) return false
  return true

─────────────────────────────────────────────────────────────
STEP 6 — Add engagement select to the filter bar
─────────────────────────────────────────────────────────────

In the existing filter bar div, add a new select after the
status select and before the dueDateSort select:

  <select
    value={engagementFilter}
    onChange={(e) => setEngagementFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Engagements</option>
    {uniqueEngagementIds.map((id) => (
      <option key={id} value={id}>
        {engagementMap[id] ?? id}
      </option>
    ))}
  </select>

─────────────────────────────────────────────────────────────
STEP 7 — Update clear filters button and count span
─────────────────────────────────────────────────────────────

Find the existing clear filters button onClick:
  onClick={() => { setClientFilter('all'); setStatusFilter('all'); setDueDateSort('asc') }}

Replace with:
  onClick={() => { setClientFilter('all'); setEngagementFilter('all'); setStatusFilter('all'); setDueDateSort('asc') }}

Find the two existing visibility conditions:
  {(clientFilter !== 'all' || statusFilter !== 'all') && (

Replace both with:
  {(clientFilter !== 'all' || engagementFilter !== 'all' || statusFilter !== 'all') && (

─────────────────────────────────────────────────────────────
STEP 8 — Update empty state condition
─────────────────────────────────────────────────────────────

Find:
  filtered.length === 0 && search === '' && clientFilter === 'all' && statusFilter === 'all'

Replace with:
  filtered.length === 0 && search === '' && clientFilter === 'all' && engagementFilter === 'all' && statusFilter === 'all'

─────────────────────────────────────────────────────────────
AFTER ALL CHANGES
─────────────────────────────────────────────────────────────
Report every line changed. Do not touch any other file.
Do not run any backend or alembic commands.