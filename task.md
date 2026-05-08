## STANDING RULES
- Never use native_enum=True for enums with dots or special characters
- Background tasks must create their own SessionLocal() session in try/finally
- Routers are thin — no business logic
- Every file starts with a path comment
- Do not run migrations — backend schema is unchanged

## TASK: Wire the Client Portal Frontend to Real API Data

The client portal frontend currently reads from hardcoded mock arrays in
`frontend/src/lib/mock/portal.ts`. The backend portal endpoints are fully
built and working. This task replaces the mock data with real API calls
across all four portal tabs: To-do, Documents, Invoices, and Messages.

The portal uses a separate JWT from the staff side. The portal token is
stored in localStorage under the key `portal_token` (or wherever the
current portal auth flow stores it after magic link exchange). Read the
existing portal auth flow before assuming the key name.

---

## STEP 1 — Audit the current portal structure

Read these files in full before writing any code:

1. `frontend/src/lib/mock/portal.ts` — understand what mock data exists
2. `frontend/src/app/portal/` — find all portal page and component files
3. `frontend/src/lib/` — find any existing portal API client or axios instance
4. The portal auth page at `/portal/auth` — understand how the token is stored after magic link exchange

Report back exactly:
- Where the portal JWT is stored after login (localStorage key, cookie name, etc.)
- Which components currently import from mock/portal.ts
- Whether a portal-specific axios/fetch wrapper already exists or needs to be created

Do NOT write any code yet. Just report the findings.

---

## STEP 2 — Create a portal API client

Create `frontend/src/lib/portal-api.ts`.

This is a thin fetch wrapper that:
- Reads the portal JWT from wherever Step 1 confirmed it is stored
- Attaches it as `Authorization: Bearer {token}` on every request
- Points at the Next.js proxy route (same pattern as the staff API client — use `/api/` prefix if a proxy exists, or direct to backend if not — check how the staff API client works and match the pattern)
- Exports typed fetch functions for each portal endpoint

Functions to export:

```typescript
// Returns PaginatedResponse<PortalInvoice>
export async function getPortalInvoices(): Promise<PortalInvoicesResponse>

// Returns list of portal documents
export async function getPortalDocuments(): Promise<PortalDocument[]>

// Returns list of portal messages for a client
export async function getPortalMessages(clientId: string): Promise<PortalMessage[]>

// Send a message from the client
export async function sendPortalMessage(clientId: string, body: string): Promise<PortalMessage>

// Returns portal dashboard (active engagements, pending signatures, unread count)
export async function getPortalDashboard(): Promise<PortalDashboard>

// Get unread message count
export async function getPortalUnreadCount(clientId: string): Promise<number>
```

Define TypeScript interfaces for each response type based on the backend
schemas in the codebase snapshot:

- `PortalInvoice` — matches `PortalInvoiceOut` schema (id, invoice_number, total_amount, status, due_date, line_items, etc.)
- `PortalDocument` — matches the `/portal/documents` response shape (id, name, uploaded_at, file_type, file_size_kb, uploaded_by)
- `PortalMessage` — matches `ClientMessageOut` (id, body, sender_role, sender_name, created_at)
- `PortalDashboard` — matches `PortalDashboardOut` (active_engagements, pending_signatures, pending_document_requests, unread_notification_count)

---

## STEP 3 — Wire the Invoices tab

Find the portal Invoices component (currently imports from mock/portal.ts).

Replace the mock import with a real call to `getPortalInvoices()`.

Requirements:
- Show a loading skeleton while fetching (match the existing skeleton pattern used elsewhere in the app)
- Show an empty state if no invoices returned
- Error state if the fetch fails — simple "Something went wrong" message with a retry button
- The Pay Now button already exists — leave it in place, do not change its behavior
- Display: invoice number, amount, status badge, due date, issued date
- Status badges must use the existing status color system (sent=blue, paid=green, overdue=red)

---

## STEP 4 — Wire the Documents tab

Find the portal Documents component.

Replace mock import with a real call to `getPortalDocuments()`.

Requirements:
- Loading skeleton while fetching
- Empty state: "No documents yet. Your firm will share documents here."
- Display: filename, uploaded date, file type badge, file size
- uploaded_by field: if "firm" show firm name, if "client" show "Uploaded by you"
- Do NOT add a download button — the portal document download requires a separate presigned URL endpoint that isn't in scope here. Just show the list.

---

## STEP 5 — Wire the Messages tab

Find the portal Messages component.

Replace mock import with real calls to `getPortalMessages(clientId)`.

The clientId needs to come from the portal JWT payload (the `sub` claim is the client_id). Decode the JWT on the client side to extract it — use `jwt-decode` if already installed, or parse the base64 payload manually (no signature verification needed client-side).

Requirements:
- Load messages on mount
- Show sender name and timestamp on each message
- Messages from sender_role="staff" appear on the left
- Messages from sender_role="client" appear on the right
- Compose box at the bottom calls `sendPortalMessage(clientId, body)`
- Optimistic UI: message appears immediately on send, before API confirms
- Loading skeleton while initial fetch is in progress
- Empty state: "No messages yet."

---

## STEP 6 — Wire the To-do tab

The To-do tab shows pending signatures and pending document requests.

Call `getPortalDashboard()` which returns:
- `pending_signatures` — list of signature envelopes awaiting signing
- `pending_document_requests` — currently returns empty list (backend placeholder) — that's fine, render nothing for this section if empty
- `active_engagements` — show engagement name and status

Requirements:
- Pending signatures: show subject, sent_at date, and a "Sign" button (button can link to the envelope or just show a placeholder — Dropbox Sign flow is separate)
- Active engagements: show name and status badge
- Loading skeleton while fetching
- Empty state for each section if nothing pending: "You're all caught up."

---

## STEP 7 — Wire the portal /me endpoint for firm name display

The portal top bar currently shows a hardcoded firm name. 

Call `GET /portal/me` on portal load. It returns:
```json
{ "client_id": "...", "client_name": "...", "firm_name": "..." }
```

Store this in component state or a simple context. Use `firm_name` in the portal top bar and `client_name` in the "Hello, [First Name]" greeting on the To-do tab. Extract first name from client_name by splitting on space and taking the first element.

---

## STEP 8 — Remove mock imports

After all tabs are wired and working:

1. Check that nothing in the portal still imports from `frontend/src/lib/mock/portal.ts`
2. Delete `frontend/src/lib/mock/portal.ts`
3. Do NOT delete `frontend/src/lib/mock/tasks.ts` — the staff task list may still use it

---

## STEP 9 — Verify

Check that:
- The portal compiles with no TypeScript errors (`npx tsc --noEmit` in the frontend directory)
- No remaining imports from mock/portal.ts
- Each tab renders a loading state, an empty state, and a data state (can be verified visually if the DB has seed data, or just confirmed the component structure handles all three cases)

Report every file modified and what changed in each one.