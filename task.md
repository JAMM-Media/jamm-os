STANDING RULES — ALWAYS FOLLOW THESE

Product name is JAMM PX. Never refer to it as JAMM OS.

Domain language — never substitute synonyms:
Firm = the accounting business. Client = the firm's customer. Engagement = unit of billable work, never "project". Task = discrete action item. Staff = firm employees. Firm Owner = admin-level user.

Tech stack — never deviate without explicit instruction:
Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0 (Mapped[] syntax only), Pydantic v2 (model_dump() and field_validator() only), Alembic, Uvicorn + Gunicorn, APScheduler, Argon2, JWT via python-jose, slowapi.
Frontend: Next.js 14+ App Router, TypeScript always, Tailwind CSS, shadcn/ui, Axios with JWT interceptor, TanStack Query.

Architecture rules — enforce always:
- Routers are thin — no business logic ever.
- Tenant isolation is absolute — every query scoped to firm_id without exception.
- Every generated file starts with a path comment.

Windows / PowerShell:
- No && chaining — separate commands
- Quoted paths for directories with parentheses

---

PHASE-SPECIFIC INSTRUCTIONS — Document archive (is_superseded surfacing)

Three parts. No migration needed.

---

PART 1 — BACKEND: add is_superseded to portal documents response

File: app/api/portal.py

Find the portal_list_documents function. It returns a list of dicts. Add is_superseded to each dict:

            "is_superseded": d.is_superseded,

That is the only backend change.

---

PART 2 — CLIENT DETAIL PAGE: wire up documents tab and split active/archived

File: frontend/src/app/clients/[id]/page.tsx

The documents tab currently shows a blank empty state. Replace it with a real document list fetched from the API.

Add these state variables:
  const [clientDocs, setClientDocs] = useState<Document[]>([])
  const [docsLoading, setDocsLoading] = useState(false)
  const [showArchived, setShowArchived] = useState(false)

The Document type is already imported from '@/lib/api/documents'.

Add a useEffect that fires when activeTab === 'documents' and clientId is set:
  setDocsLoading(true)
  api.get(`/documents/?client_id=${clientId}&limit=100`)
    .then((r) => setClientDocs(r.data?.items ?? []))
    .catch(() => {})
    .finally(() => setDocsLoading(false))

Replace the documents tab empty state with the following layout:

Active documents section:
- Filter clientDocs where is_superseded is false or null
- If loading show 3 skeleton rows (same pattern as other tabs)
- If active docs is empty and archived docs is also empty show the existing empty state
- If active docs is empty but archived exist show a muted message "All documents are archived"
- Render active docs using the existing DocumentTable component passing the active docs array

Archived documents section (only render if clientDocs has any where is_superseded is true):
- A toggle row: "Archived ({count})" label in muted 11px uppercase style, with a ChevronDown/ChevronUp icon button that toggles showArchived state
- When showArchived is true render a DocumentTable with only the superseded docs, with 0.6 opacity wrapper
- The DocumentTable already has the "Mark as current" / "Mark as superseded" toggle built in so no extra controls needed

---

PART 3 — PORTAL DOCUMENTS: split active and archived

File: frontend/src/components/portal/PortalDocuments.tsx

Step 1 — Add is_superseded to the PortalDocument interface in frontend/src/lib/portal-api.ts:
  is_superseded: boolean

Step 2 — In PortalDocuments.tsx, derive two lists from documents:
  const activeDocs = documents.filter((d) => !d.is_superseded)
  const archivedDocs = documents.filter((d) => d.is_superseded)

Add state: const [showArchived, setShowArchived] = useState(false)

Step 3 — Update the render section:
- Replace the flat documents.map with activeDocs.map using the exact same card style
- Update the count label to show active count: "Documents ({activeDocs.length})"
- Below the active list, if archivedDocs.length > 0 render:
  - A toggle row styled consistently with the portal card style: "Archived ({archivedDocs.length})" label in mutedText color, 11px, with a chevron button that toggles showArchived
  - When showArchived is true render the archived docs using the same card style but with 0.6 opacity and a small "Archived" pill badge (bg: cardColor, text: mutedText, 10px) next to the document name

---

VERIFICATION

1. npx tsc --noEmit in frontend/ passes with no errors
2. Confirm portal documents endpoint now returns is_superseded field
3. Confirm client detail documents tab loads real documents and splits active/archived correctly
4. Confirm portal documents component splits active/archived with working toggle