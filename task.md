═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend changes only. Three files total.

═══════════════════════════════════════════════════════════════
TASK: Add filters to Clients, Engagements, and Tasks pages
═══════════════════════════════════════════════════════════════

The select dropdown style used throughout is:
  className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border
  dark:border-dark-border bg-surface-card dark:bg-dark-card
  text-brand dark:text-[#EDEEF0] cursor-pointer"

Use this exact className on every new <select> element.

─────────────────────────────────────────────────────────────
FILE 1 — frontend/src/app/clients/page.tsx
─────────────────────────────────────────────────────────────

ADD two new state variables directly after the existing
const [search, setSearch] = useState('') line:

  const [entityFilter, setEntityFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')

UPDATE the filtered const to apply both new filters:

  BEFORE:
    const filtered = clients.filter((c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.email ?? '').toLowerCase().includes(search.toLowerCase())
    )

  AFTER:
    const filtered = clients.filter((c) => {
      if (
        search &&
        !c.name.toLowerCase().includes(search.toLowerCase()) &&
        !(c.email ?? '').toLowerCase().includes(search.toLowerCase())
      ) return false
      if (entityFilter !== 'all' && c.entityType !== entityFilter) return false
      if (statusFilter === 'active' && !c.isActive) return false
      if (statusFilter === 'inactive' && c.isActive) return false
      return true
    })

ADD a filter bar div immediately after the closing </div> of
the existing toolbar div (the one containing search input,
ViewToggle, and + New Client button). Insert:

  <div className="flex items-center gap-2 flex-wrap">
    <select
      value={entityFilter}
      onChange={(e) => setEntityFilter(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Entity Types</option>
      <option value="individual">Individual</option>
      <option value="business">Business</option>
      <option value="trust">Trust</option>
      <option value="estate">Estate</option>
    </select>

    <select
      value={statusFilter}
      onChange={(e) => setStatusFilter(e.target.value)}
      className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
    >
      <option value="all">All Clients</option>
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
    </select>

    {(entityFilter !== 'all' || statusFilter !== 'all') && (
      <button
        onClick={() => { setEntityFilter('all'); setStatusFilter('all') }}
        className="text-[11px] text-[#6B7280] hover:text-brand underline"
      >
        Clear filters
      </button>
    )}

    {(entityFilter !== 'all' || statusFilter !== 'all') && (
      <span className="text-[11px] text-[#6B7280]">
        Showing {filtered.length} of {clients.length} clients
      </span>
    )}
  </div>

─────────────────────────────────────────────────────────────
FILE 2 — Engagements page
Check which path exists and edit the correct one:
  frontend/src/app/(dashboard)/engagements/page.tsx
  frontend/src/app/engagements/page.tsx
─────────────────────────────────────────────────────────────

ADD two new state variables directly after the existing
const [formFilter, setFormFilter] = useState<string>('all') line:

  const [clientFilter, setClientFilter] = useState<string>('all')
  const [dueDateSort, setDueDateSort] = useState<string>('asc')

UPDATE the filtered const. Replace the entire filtered const
with:

  const filtered = allEngagements
    .filter((e) => {
      if (search && !e.name.toLowerCase().includes(search.toLowerCase())) return false
      if (statusFilter !== 'all' && e.status !== statusFilter) return false
      if (categoryFilter !== 'all' && getEngagementCategory(e.engagementType) !== categoryFilter) return false
      if (formFilter !== 'all' && e.engagementType !== formFilter) return false
      if (clientFilter !== 'all' && e.clientId !== clientFilter) return false
      return true
    })
    .sort((a, b) => {
      const aDate = a.deadline ? new Date(a.deadline).getTime() : Infinity
      const bDate = b.deadline ? new Date(b.deadline).getTime() : Infinity
      return dueDateSort === 'asc' ? aDate - bDate : bDate - aDate
    })

NOTE: The deadline field on an engagement may be named
filing_deadline, deadline, or filingDeadline — check the
Engagement type definition in the file and use whatever field
name holds the primary deadline date. Use that field name in
the sort function above.

ADD two new selects to the existing filter bar div, after the
last existing select block (after the payroll subtype filter)
and before the clear filters button:

  {/* Client filter */}
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

  {/* Due date sort */}
  <select
    value={dueDateSort}
    onChange={(e) => setDueDateSort(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="asc">Due Date ↑ Earliest</option>
    <option value="desc">Due Date ↓ Latest</option>
  </select>

UPDATE the existing clear filters button onClick to also reset
the two new filters:
  BEFORE:
    onClick={() => { setStatusFilter('all'); setCategoryFilter('all'); setFormFilter('all') }}
  AFTER:
    onClick={() => { setStatusFilter('all'); setCategoryFilter('all'); setFormFilter('all'); setClientFilter('all'); setDueDateSort('asc') }}

UPDATE the existing clear filters button visibility condition:
  BEFORE:
    {(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all') && (
  AFTER:
    {(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all' || clientFilter !== 'all') && (

NOTE: dueDateSort is intentionally excluded from the clear
filters condition — it always has a value (asc or desc) and
is not a filter that needs clearing, just a sort direction.

Apply the same condition update to the "Showing X of Y" count
span visibility check directly below it.

─────────────────────────────────────────────────────────────
FILE 3 — frontend/src/app/tasks/page.tsx
─────────────────────────────────────────────────────────────

ADD two new state variables directly after the existing
const [statusFilter, setStatusFilter] = useState<string>('all') line:

  const [clientFilter, setClientFilter] = useState<string>('all')
  const [dueDateSort, setDueDateSort] = useState<string>('asc')

UPDATE the filtered const. Replace the entire filtered const
including its sort with:

  const filtered = allTasks
    .filter((t) => {
      if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false
      if (statusFilter !== 'all' && t.status !== statusFilter) return false
      if (clientFilter !== 'all' && t.clientId !== clientFilter) return false
      if (myTasksOnly && t.assignedTo !== user?.id) return false
      return true
    })
    .sort((a, b) => {
      const aDate = a.dueDate ? new Date(a.dueDate).getTime() : Infinity
      const bDate = b.dueDate ? new Date(b.dueDate).getTime() : Infinity
      return dueDateSort === 'asc' ? aDate - bDate : bDate - aDate
    })

NOTE: The due date field on a task may be named dueDate or
due_date — check the Task type definition in the file and use
the correct field name in the sort function above.

The tasks page already has a filter bar. ADD two new selects
to that filter bar, after the existing status select and
before the My Tasks button:

  {/* Client filter */}
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

  {/* Due date sort */}
  <select
    value={dueDateSort}
    onChange={(e) => setDueDateSort(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="asc">Due Date ↑ Earliest</option>
    <option value="desc">Due Date ↓ Latest</option>
  </select>

The tasks page already has a clear filters button and count
span. UPDATE their visibility conditions to include the client
filter but NOT dueDateSort (same reasoning as engagements —
sort direction always has a value, not a filter to clear):

  Add: || clientFilter !== 'all'
  to any existing condition that controls their visibility.

UPDATE the clear filters onClick to also reset clientFilter
but reset dueDateSort back to 'asc' not 'none':

  Add: setClientFilter('all'); setDueDateSort('asc')

─────────────────────────────────────────────────────────────
AFTER ALL THREE FILES
─────────────────────────────────────────────────────────────
Report every file modified and the exact lines changed.
Do not run any backend or alembic commands.