═══════════════════════════════════════════════════════════════
STANDING RULES — READ FIRST, ENFORCE ALWAYS
═══════════════════════════════════════════════════════════════
- Never use native_enum=True for enums with dots. Always sa.Enum(MyEnum, native_enum=False).
- Every file starts with a path comment.
- Routers are thin — no business logic ever.
- Every background task creates its own SessionLocal() in try/finally.
- Never modify any migration file that already exists.
- Run all scripts with python -m scripts.name (never python scripts/name.py).
- TypeScript errors fail the Vercel build — fix all type errors before finishing.
- Never add console.log statements to production code.

═══════════════════════════════════════════════════════════════
MIGRATION PROCEDURE — FOLLOW EVERY TIME A MODEL CHANGES
═══════════════════════════════════════════════════════════════
1. alembic current          — confirm starting state
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it touches tables beyond
   what you just changed, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current          — confirm at new head

═══════════════════════════════════════════════════════════════
TASK: QA bug fixes + index_consent field
Three passes. Complete each pass fully before starting the next.
═══════════════════════════════════════════════════════════════


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASS 1 — BACKEND: index_consent field on Firm + behavioral log guard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1A — Add index_consent to the Firm model
-----------------------------------------------
File: app/models/firm.py

Add the following field to the Firm class, after the
plan_override field and before created_at:

    index_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Firm has consented to contribute anonymized data to the JAMM Intelligence Index.",
    )

Do not change any other field or relationship.


STEP 1B — Run migration
------------------------
Follow the migration procedure exactly.
Use this description: "add index_consent to firms"

The generated migration should contain exactly one change:
adding the index_consent column to the firms table.
If it contains anything else, delete it and write a clean
manual migration that only adds this one column.


STEP 1C — Add index_consent guard to behavioral_log service
-------------------------------------------------------------
File: app/services/behavioral_log.py

Replace the entire log_event function with the following.
Do not change any imports or anything outside this function:

def log_event(
    *,
    event_type: str,
    firm_id: uuid.UUID,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
    session_id: Optional[uuid.UUID] = None,
) -> None:
    db = None
    try:
        db = SessionLocal()

        # Honour the firm's index consent choice.
        # Firms that opted out produce zero behavioral event rows.
        from app.models.firm import Firm
        firm = db.get(Firm, firm_id)
        if firm is None or not firm.index_consent:
            return

        event = BehavioralEvent(
            firm_id=firm_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            extra_metadata=metadata,
            session_id=session_id,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        log.warning("behavioral_log.log_event failed: %s", exc)
    finally:
        if db is not None:
            db.close()


STEP 1D — Verify
-----------------
Run: alembic current
Confirm the output shows the new migration head.

Run: python -c "from app.models.firm import Firm; print('OK')"
Confirm it prints OK with no import errors.

Report the alembic current output and the python check result.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASS 2 — FRONTEND FIXES (CSS + component bugs)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2A — Fix overflow:hidden table clipping (Issues 3, 14, 20)
----------------------------------------------------------------
This is the same root cause across three pages. The table wrapper
div uses overflow-hidden with a fixed computed height, clipping rows.

Fix each file below by changing the outer table container div:
  FROM: className="... overflow-hidden ..."
  TO:   className="... overflow-auto ..."   (change hidden → auto)

Also ensure the container has no fixed height class (h-[Npx] or
similar) that would clip content. Remove any fixed height if present.

Files to fix:
  frontend/src/components/billing/InvoiceTable.tsx
    — The outermost div has className containing "overflow-hidden"
    — Change overflow-hidden to overflow-auto on that div only

  frontend/src/components/clients/ClientTable.tsx  (or ClientList.tsx)
    — Same fix: overflow-hidden → overflow-auto on the table wrapper

  frontend/src/components/tasks/TaskTable.tsx
    — Same fix on the table wrapper div

After fixing, the table must be scrollable when content exceeds the
container height, and all rows must be reachable by scrolling.


STEP 2B — Fix Toaster pointer-events bug (Issues 30, 31, 32)
--------------------------------------------------------------
The Sonner toast container stays in the DOM after toasts dismiss
and intercepts pointer events across the right portion of the page,
blocking Settings radio buttons, the Automations tab, and all
automation toggles.

File: frontend/src/components/ui/sonner.tsx

Add the containerStyle prop to the <Sonner> component to ensure
the toast container never intercepts pointer events when empty:

  <Sonner
    theme={theme as ToasterProps["theme"]}
    className="toaster group"
    containerAriaLabel="Notifications"
    style={{ pointerEvents: "none" }}
    toastOptions={{
      style: { pointerEvents: "auto" },
      classNames: {
        toast: "cn-toast",
      },
    }}
    icons={{ ...existing icons unchanged... }}
    {...props}
  />

Keep all existing icon definitions and style props exactly as they
are. Only add the two new style/toastOptions changes shown above.
The container gets pointerEvents none; individual toasts get
pointerEvents auto so they remain interactive.


STEP 2C — Fix status badge wrapping (Issue 11)
-----------------------------------------------
Status badge text wraps to two lines ("In / Review", "Not / Started")
because the badge container lacks white-space: nowrap.

File: frontend/src/components/ui/StatusBadge.tsx

Find the badge span/div element that renders the status text.
Add whitespace-nowrap to its className.

Example — if the current class is:
  className="text-[11px] font-medium px-2 py-0.5 rounded-full ..."
Change to:
  className="text-[11px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ..."


STEP 2D — Fix New Invoice button (Issue 21)
--------------------------------------------
The "+ New Invoice" button on the billing page has no onClick handler.

File: frontend/src/app/billing/page.tsx

1. Add a state variable for the new invoice modal:
   const [newInvoiceOpen, setNewInvoiceOpen] = useState(false)

2. Wire the button:
   Change:
     <button className="...">+ New Invoice</button>
   To:
     <button
       onClick={() => setNewInvoiceOpen(true)}
       className="..."
     >
       + New Invoice
     </button>

3. Import and render the NewInvoiceModal component below the button.
   If NewInvoiceModal does not exist yet, create a minimal stub at
   frontend/src/components/billing/NewInvoiceModal.tsx that renders
   a modal with the title "New Invoice" and a close button, and
   accepts props: open (boolean) and onClose (() => void).
   Wire it in billing/page.tsx:
     <NewInvoiceModal
       open={newInvoiceOpen}
       onClose={() => setNewInvoiceOpen(false)}
     />

   The modal does not need to be fully functional yet — it just needs
   to open and close correctly so the button is no longer dead.


STEP 2E — Fix invoice row navigation (Issue 23)
------------------------------------------------
Invoice rows in InvoiceTable currently navigate to the client page
on row click. They should navigate to the invoice detail page.
The invoice detail page already exists at /billing/[id].

File: frontend/src/components/billing/InvoiceTable.tsx

Find the row onClick handler:
  onClick={() => router.push(`/clients/${inv.clientId}`)}

Change it to:
  onClick={() => router.push(`/billing/${inv.id}`)}

The client name cell already has its own stopPropagation + push to
/clients/[id], so clicking the client name still goes to the client.
Only the row-level navigation changes.


STEP 2F — Fix client billing tab showing no invoices (Issue 25)
----------------------------------------------------------------
The Billing tab on the client detail page shows "No invoices yet"
even when the client has invoices. The API list call is missing the
client_id filter.

Find the file that renders the client detail Billing tab.
It will be in: frontend/src/app/clients/[id]/page.tsx
or: frontend/src/components/clients/tabs/BillingTab.tsx

Find where invoices are fetched for this tab. The call will look like:
  invoicesApi.list(0, 50)
  or: invoicesApi.list({ skip: 0, limit: 50 })

Change it to pass the clientId:
  invoicesApi.list(0, 50, clientId)
  or however the invoicesApi.list function accepts a client_id filter.

Check frontend/src/lib/api/invoices.ts to confirm the list function
signature and what parameter name it uses for client filtering.
Pass the client ID from the page params/props.


STEP 2G — Fix billing search to include client names (Issue 24)
----------------------------------------------------------------
The billing page search only matches on invoice number.
The no-results message says "Try a different invoice number or
client name" but client name search doesn't work.

File: frontend/src/app/billing/page.tsx

Find the filtered array:
  const filtered = invoices.filter((inv) =>
    inv.invoiceNumber.toLowerCase().includes(search.toLowerCase())
  )

Change it to also match client names using the clientMap:
  const filtered = invoices.filter((inv) => {
    const q = search.toLowerCase()
    const clientName = (clientMap[inv.clientId] ?? '').toLowerCase()
    return (
      inv.invoiceNumber.toLowerCase().includes(q) ||
      clientName.includes(q)
    )
  })


STEP 2H — Fix New Engagement modal missing client field (Issue 12)
------------------------------------------------------------------
The New Engagement creation modal has no Client field. Engagements
are created unassigned.

Find the NewEngagementModal component:
  frontend/src/components/engagements/NewEngagementModal.tsx
  (or wherever the new engagement form lives)

1. Add a client_id field to the form state, defaulting to ''.

2. Add a Client dropdown to the form UI, before or after the
   Title field. Fetch the client list using clientsApi.list(0, 100)
   inside the modal (or accept clients as a prop from the parent).
   Render a <select> or SelectInput with options from the client list.
   Label: "Client". Mark as required.

3. Include client_id in the payload sent to engagementsApi.create().
   Check frontend/src/lib/api/engagements.ts for the create function
   signature and what field name it expects for the client.

4. Add validation: if client_id is empty, show "Client is required."
   and do not submit.


STEP 2I — Fix task assigned-to showing UUID (Issue 15)
-------------------------------------------------------
Tasks created via the UI show the raw UUID in the Assigned To column
instead of the staff member's name. The staff list is fetched but the
display layer fails to resolve UUID → name.

Find the TaskTable component:
  frontend/src/components/tasks/TaskTable.tsx

Look for where assigned_to is displayed. It likely renders
task.assignedTo directly without a lookup. Fix it to resolve against
a staff/users map, the same way InvoiceTable resolves clientId → name
using clientMap.

1. In the parent page (frontend/src/app/tasks/page.tsx), fetch the
   users list if not already fetched:
   const { data: usersData } = useFetch(() => api.get('/users/'), [])
   Build a userMap: Record<string, string> mapping user id → full_name.

2. Pass userMap down to TaskTable as a prop.

3. In TaskTable, display:
   userMap[task.assignedTo] ?? task.assignedTo
   (falls back to the raw value if lookup fails, but resolves when
   the map is populated)

Check the existing Task type in frontend/src/lib/api to confirm the
exact field name (assignedTo vs assigned_to).


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASS 3 — FRONTEND FIXES (engagement extension modal + autocomplete)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 3A — Fix File Extension modal taller than viewport (Issue 9)
-----------------------------------------------------------------
The extension modal overflows the viewport. The title and close
button are above the visible area and Cancel does not work.

Find the extension modal component. It will be in:
  frontend/src/components/engagements/FileExtensionModal.tsx
  or similar.

Apply all of the following fixes:

1. The modal container must not exceed the viewport height.
   Wrap the modal content in:
     <div className="max-h-[90vh] overflow-y-auto flex flex-col">
   This allows the modal to scroll internally rather than overflow.

2. The header (title + X close button) must be sticky at the top
   of the scrollable area so it is always visible:
     <div className="sticky top-0 bg-white dark:bg-dark-card z-10
                     flex items-center justify-between p-4 border-b
                     border-surface-border dark:border-dark-border">
       {/* title and X button here */}
     </div>

3. The Cancel button must work. Find the Cancel button and confirm
   it has a working onClick that calls the onClose/onCancel prop.
   If the onClick is missing or undefined, wire it correctly.

4. Escape key must close the modal. If the modal uses the shared
   Modal component, this is already handled. If it is a custom
   implementation, add:
     useEffect(() => {
       function handleKey(e: KeyboardEvent) {
         if (e.key === 'Escape') onClose()
       }
       document.addEventListener('keydown', handleKey)
       return () => document.removeEventListener('keydown', handleKey)
     }, [onClose])


STEP 3B — Fix invite form credential autofill (Issue 28)
---------------------------------------------------------
The team member invite form in Settings autofills with the logged-in
owner's email and password because autocomplete is not disabled.

File: frontend/src/app/settings/page.tsx

Find the invite form inputs. Add autocomplete attributes:

  Email input:
    add: autoComplete="off"

  Password input:
    add: autoComplete="new-password"

  Full name input:
    add: autoComplete="off"

These three attribute additions prevent browser credential autofill
on the invite form while leaving the login form unaffected.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL STEP — TypeScript check + deploy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After completing all steps above:

1. Run: cd frontend && npx tsc --noEmit
   Fix every TypeScript error before proceeding.
   Do not skip this step — TypeScript errors fail the Vercel build.

2. Run: cd frontend && npm run build
   Confirm build succeeds with no errors.

3. Report:
   - Which files were modified in each pass
   - The result of the TypeScript check
   - The result of npm run build
   - The alembic current output after Pass 1
   - Any errors encountered and how they were resolved