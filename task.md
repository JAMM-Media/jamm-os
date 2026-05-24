═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never run alembic commands.
- Never modify any model, migration, or backend file.
- Frontend changes only. Four files total.

═══════════════════════════════════════════════════════════════
TASK: Add client name to engagement filter dropdowns
═══════════════════════════════════════════════════════════════

The goal is to change engagement dropdown options from:
  "2024 Individual Tax Return — Form 1040"
to:
  "2024 Individual Tax Return — Form 1040 (Sarah Chen)"

This applies to four pages. Each page already has engagements
and clients data loaded — we just need to update the option
label to include the client name.

─────────────────────────────────────────────────────────────
FILE 1 — frontend/src/app/tasks/page.tsx
─────────────────────────────────────────────────────────────

This page already has clientsData and engagementsData loaded.
It already has a clientMap built from clientsData.

Find the engagement filter select options. It will look like:

  {(engagementsData?.items ?? [])
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => (
      <option key={e.id} value={e.id}>{e.name}</option>
    ))}

Replace the option label:
  BEFORE: <option key={e.id} value={e.id}>{e.name}</option>
  AFTER:  <option key={e.id} value={e.id}>{e.name}{clientMap[e.clientId] ? ` (${clientMap[e.clientId]})` : ''}</option>

─────────────────────────────────────────────────────────────
FILE 2 — frontend/src/app/engagements/page.tsx
─────────────────────────────────────────────────────────────

This page already has clientsData and a clientMap built from it.

Find the client filter select — this page filters engagements
by client, not by engagement name, so no change needed there.

Find the engagement filter select options for the client
dropdown. Actually this page does not have an engagement
dropdown — it IS the engagements list. Skip this file.

─────────────────────────────────────────────────────────────
FILE 2 — frontend/src/app/billing/page.tsx
─────────────────────────────────────────────────────────────

This page has clientsData, clientMap, engagementsData, and
engagementMap already built.

Find the engagement filter select options:

  {uniqueEngagementIds.map((id) => (
    <option key={id} value={id}>
      {engagementMap[id] ?? id}
    </option>
  ))}

Replace with:

  {uniqueEngagementIds.map((id) => {
    const eng = (engagementsData?.items ?? []).find((e) => e.id === id)
    const clientName = eng ? (clientMap[eng.clientId] ?? '') : ''
    const label = engagementMap[id] ?? id
    return (
      <option key={id} value={id}>
        {label}{clientName ? ` (${clientName})` : ''}
      </option>
    )
  })}

─────────────────────────────────────────────────────────────
FILE 3 — frontend/src/app/(dashboard)/timesheets/page.tsx
─────────────────────────────────────────────────────────────

This page has engagementList (id + name only) but no clients
data. We need to add a clients fetch and build a client map.

STEP 1 — Add clientsApi to the import.
The page currently imports api from '@/lib/api'.
Check if clientsApi is already imported — if not add it:
  import { clientsApi } from '@/lib/api'

STEP 2 — Add clientMap state and fetch.
Directly after the engagementList state and useEffect, add:

  const [clientMap, setClientMap] = useState<Record<string, string>>({})

  useEffect(() => {
    api.get('/clients/?limit=100').then((r) => {
      const map: Record<string, string> = {}
      for (const c of r.data?.items ?? []) map[c.id] = c.name
      setClientMap(map)
    }).catch(() => {})
  }, [])

STEP 3 — Update the engagement dropdown option label.

Find the engagement select options:
  {engagementList
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => (
      <option key={e.id} value={e.id}>{e.name}</option>
    ))}

Replace with:
  {engagementList
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => (
      <option key={e.id} value={e.id}>
        {e.name}{e.clientName ? ` (${e.clientName})` : ''}
      </option>
    ))}

STEP 4 — engagementList items need clientName.
The engagementList state is typed as { id: string; name: string }[].
Update the type and the fetch to include clientName:

Update the useState type:
  BEFORE: const [engagementList, setEngagementList] = useState<{ id: string; name: string }[]>([])
  AFTER:  const [engagementList, setEngagementList] = useState<{ id: string; name: string; clientName: string }[]>([])

Update the useEffect mapping:
  BEFORE:
    setEngagementList(items.map((e: { id: string; name: string }) => ({ id: e.id, name: e.name })))
  AFTER:
    setEngagementList(items.map((e: { id: string; name: string; client_id?: string }) => ({
      id: e.id,
      name: e.name,
      clientName: clientMap[e.client_id ?? ''] ?? '',
    })))

NOTE: The clientMap fetch and the engagementList fetch both run
in separate useEffects. The engagementList useEffect does not
depend on clientMap so clientName may be empty on first load.
To fix this, merge the two fetches into one useEffect that
fetches clients first then engagements:

Replace the separate engagements useEffect with:

  useEffect(() => {
    api.get('/clients/?limit=100').then((r) => {
      const map: Record<string, string> = {}
      for (const c of r.data?.items ?? []) map[c.id] = c.name
      setClientMap(map)
      return map
    }).then((map) => {
      return api.get('/engagements/?limit=100').then((r) => {
        const items = r.data?.items ?? []
        setEngagementList(items.map((e: { id: string; name: string; client_id?: string }) => ({
          id: e.id,
          name: e.name,
          clientName: map[e.client_id ?? ''] ?? '',
        })))
      })
    }).catch(() => {})
  }, [])

─────────────────────────────────────────────────────────────
FILE 4 — frontend/src/app/documents/page.tsx
─────────────────────────────────────────────────────────────

The documents engagement filter uses engagementTitle which is
already a string like "2024 Individual Tax Return — Form 1040"
pulled directly from the document object. It does not use IDs
so there is no clientMap lookup possible.

However the uniqueEngagements list is built from
d.engagementTitle which is just the engagement name with no
client info. To add client name here we would need to change
the data model.

Skip this file — the documents engagement filter shows
engagement titles as-is which is acceptable since documents
are already filtered by client first in practice.

─────────────────────────────────────────────────────────────
AFTER ALL FILES
─────────────────────────────────────────────────────────────
Report every file modified and the exact lines changed.
Do not run any backend or alembic commands.