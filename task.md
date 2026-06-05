PHASE-SPECIFIC INSTRUCTIONS — Pre-launch blocker cleanup
Three items in this run: (1) remove mock data file imports, (2) the JWT refresh interceptor is already built — skip, (3) remove the index_consent gate from log_event.

---

ITEM 1 — Remove mock file dependencies and delete mock files

The frontend has a folder at frontend/src/lib/mock/ containing six files: clients.ts, dashboard.ts, documents.ts, engagements.ts, invoices.ts, tasks.ts. All real data is already coming from the live API. The mock files are only still referenced for type definitions and two utility functions. Clean this up completely.

Step 1 — Add formatCurrency and formatFileSize to frontend/src/lib/utils.ts.

Add these two functions to the bottom of the file:

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

Step 2 — Update all files that import formatCurrency or formatFileSize from mock files to import from '@/lib/utils' instead. Files affected:
- frontend/src/app/billing/[id]/page.tsx
- frontend/src/components/billing/BillingSummary.tsx
- frontend/src/components/billing/InvoiceCard.tsx
- frontend/src/components/billing/InvoiceTable.tsx
- frontend/src/components/documents/DocumentCard.tsx
- frontend/src/components/documents/DocumentTable.tsx

Step 3 — The DashboardItem type is already defined in frontend/src/lib/api/dashboard.ts. Update these two files to import DashboardItem from '@/lib/api/dashboard' instead of '@/lib/mock/dashboard':
- frontend/src/components/dashboard/DashboardSection.tsx
- frontend/src/components/dashboard/PriorityItem.tsx

Step 4 — The MockDocument type is used as a prop type in DocumentCard.tsx and DocumentTable.tsx, but the documents page already passes real API data through it. Rename MockDocument to Document in those two component files — update the interface name in the import and all usages within those files. Do not touch the mock/documents.ts file yet in this step.

Step 5 — Delete the entire frontend/src/lib/mock/ directory and all six files inside it.

Step 6 — Run: cd frontend && npx tsc --noEmit
Fix any type errors that surface. The only expected errors are any remaining references to mock types that Step 4 may have missed.

---

ITEM 2 — Remove the index_consent gate from behavioral_log.py

Open app/services/behavioral_log.py. In the log_event function, remove the following lines entirely:

        from app.models.firm import Firm
        firm = db.get(Firm, firm_id)
        if firm is None or not firm.index_consent:
            return

After removal the function should proceed directly from opening the db session to creating the BehavioralEvent. Every firm contributes data by default — no consent check, no lookup, no early return.

Do not touch the index_consent field on the Firm model or its migration. Do not remove the field from the database. Only remove the gate in log_event.

---

VERIFICATION

After both items are complete:
1. Confirm frontend/src/lib/mock/ directory no longer exists
2. Confirm npx tsc --noEmit in frontend/ passes with no errors
3. Confirm app/services/behavioral_log.py no longer imports or references Firm or index_consent
4. Run pytest from the project root and report the pass count