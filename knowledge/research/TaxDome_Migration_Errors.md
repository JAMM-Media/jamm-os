# TaxDome Migration Errors
## For JAMM Concierge Phase 4 Source Intelligence

Common errors, failure modes, and surprises firms encounter when migrating from TaxDome. The Concierge uses this to warn firms before they hit these problems.

---

## Error 1: Rows Silently Skipped Due to Assignee Name Typos

**What happens:** If the CSV includes team member assignment columns and any name is misspelled, uses a nickname, or is not comma-separated correctly, the entire row is silently skipped. No error message appears per row. The client or job is simply not imported.

**Why it matters:** Firms can lose entire client batches without knowing it. The only way to detect this is to audit the post-import count against the CSV row count.

**JAMM PX behavior:** JAMM PX does not import assignee columns from TaxDome CSVs. Assignments are set manually after import. This problem does not exist in JAMM PX's TaxDome import flow.

**What to tell firms:** After importing, compare the number of clients or engagements in JAMM PX against the number of rows in your TaxDome export. If the numbers do not match, check the import warnings report for skipped rows.

---

## Error 2: Empty Column Headers Crash the Import

**What happens:** If the CSV has any blank column header cells in the top row, TaxDome's import wizard throws a "Cannot read properties of null" error and refuses to process the entire file.

**Common cause:** Exporting from older software on Windows that adds blank trailing columns. Opening the CSV in Excel and saving it can also introduce this.

**JAMM PX behavior:** JAMM PX strips empty headers silently and processes the file. This problem does not occur.

**What to tell firms:** If your TaxDome import failed with a null error, open the CSV in a text editor (not Excel), check the first line for trailing commas with no header text, and remove them.

---

## Error 3: UTF-8 Encoding Failures

**What happens:** If the CSV is not saved in UTF-8 encoding, characters in client names may be garbled or records may fail to process entirely. Most common with names containing accented characters (Jose, Muller, etc.).

**Common cause:** Exporting from older tax software on Windows that defaults to ANSI or Latin-1 encoding.

**JAMM PX behavior:** JAMM PX's TaxDome importer accepts both UTF-8 and Latin-1 (with automatic detection and fallback). This problem does not occur.

**What to tell firms:** If client names look garbled after import, the source file was not UTF-8. Re-export from TaxDome and ensure UTF-8 encoding is selected, or use a text editor to convert the encoding before re-importing.

---

## Error 4: Client Chat History Is Gone

**What happens:** TaxDome does not export client chat message content. There is no bulk export of the message threads between firms and clients. The jobs CSV includes a "linked chats" column but this is a reference ID, not the message text.

**What this means:** Years of client communication, document exchange confirmations, to-do acknowledgments, and engagement context are permanently locked inside TaxDome. Migrating firms cannot transfer this history to JAMM PX.

**What to tell firms:** Before migrating, manually review and document any critical client communications in TaxDome that you need to reference later. Copy important threads into internal notes on the client record in JAMM PX after import. There is no automated path for this.

---

## Error 5: Recurring Invoice Templates Do Not Export

**What happens:** TaxDome's invoice export explicitly covers one-time invoices only. Recurring invoice templates, schedules, and billing configurations are not exported.

**What this means:** Every recurring retainer, subscription billing arrangement, and automatic invoice schedule must be manually recreated in JAMM PX after import.

**What to tell firms:** Before migrating, export your invoice list from TaxDome and note every recurring billing arrangement. After import, navigate to Billing in JAMM PX and recreate each recurring invoice manually. If you have the Recurring Engagement Kickoff automation preset enabled, it will create draft invoices automatically for recurring engagements going forward.

---

## Error 6: Pipeline Stage History Is Lost

**What happens:** The TaxDome jobs CSV exports only the current stage a job is in and when it entered that stage. The full history of which stages a job moved through and when is not exported.

**What this means:** Firms that use TaxDome for reporting on stage throughput, bottleneck analysis, or client engagement timelines lose all of that historical data on migration. Only the current snapshot transfers.

**What to tell firms:** JAMM PX tracks engagement status changes from the point of import forward. Historical stage progression from TaxDome cannot be reconstructed. If you need this history for audits or reporting, export the TaxDome jobs CSV before migrating and keep it as your archive.

---

## Error 7: Import-Export Row Structure Mismatch

**What happens:** TaxDome's Accounts CSV export uses one row per account with multiple contacts as additional columns. But TaxDome's own import format requires one row per contact. The file you export cannot be directly re-imported without restructuring.

**What this means for JAMM PX:** JAMM PX's TaxDome importer reads one row per client using the Account Name column. Contacts are not imported from the Accounts CSV. For multi-contact accounts (married couples, business with multiple contacts), the primary contact's email is used. Secondary contacts must be noted manually.

**What to tell firms:** If you have accounts with multiple contacts in TaxDome (joint filers, business accounts with multiple people), only the primary email in the Account Name row will transfer. Add secondary contact information manually to the client notes field in JAMM PX after import.

---

## Error 8: IRS Authorization Records Require Manual Recreation

**What happens:** TaxDome stores Form 8821 and 2848 records as PDFs in client document folders, not as structured data. There are no exportable fields for authorization type, tax years, CAF number, or effective dates.

**What this means for JAMM PX:** JAMM PX tracks IRS authorizations as first-class records with fields for form type, tax years, valid from date, and valid until date. These records must be created manually for every migrating client.

**What to tell firms:** After importing clients, navigate to each tax client's record and open the IRS Authorizations section. Create an authorization record for each client that has an active 8821 or 2848 on file. Use the PDF in TaxDome as the source for the tax years and dates. This step is required for the IRS Authorization Expiry Warning automation preset to work correctly.

---

## Error 9: CPACharge Removed January 2026

**Context:** In January 2026, TaxDome removed its CPACharge integration with minimal notice, mid-tax season. Firms that relied on CPACharge for client payments were forced to migrate payment processors during the busiest period of the year.

**What this means for JAMM PX:** JAMM PX uses Stripe Connect for all client payments. There is no CPACharge integration. Firms migrating from TaxDome post-January 2026 should already be off CPACharge. JAMM PX's Stripe integration is included at no additional cost.

**What to tell firms:** If you were using CPACharge in TaxDome, you will need to send clients a new payment link through JAMM PX's Stripe-powered portal. Existing CPACharge payment method records do not transfer. Clients pay through the JAMM PX portal invoice using a card on file with Stripe.

---

## Error 10: Deletion Is Permanent and Immediate

**What happens:** When a TaxDome account is archived, clients lose portal access immediately. When an account is deleted, all files, data, billing records, and history are permanently and unrecoverably wiped.

**What this means for migration timing:** Firms must complete all exports before archiving or deleting any accounts. TaxDome export links expire after 24 hours. The sequence must be: export everything first, then archive, then delete only when certain.

**What to tell firms:** Do not archive or delete any TaxDome accounts until your JAMM PX import is complete and verified. Once you have confirmed all clients and engagements imported correctly, you can archive TaxDome accounts safely. Delete only after you have kept the archived accounts for at least one billing cycle as a safety net.

---

## Summary: What the Concierge Should Warn Firms About Proactively

When a firm says they are migrating from TaxDome, the Concierge should surface these warnings without being asked:

1. Chat history does not transfer. Save important conversations manually before migrating.
2. Recurring invoices must be recreated manually.
3. IRS authorization records must be created manually for each client.
4. Stage history is not exported. Only current status transfers.
5. Do not delete TaxDome accounts until JAMM PX import is verified.
6. Multi-contact accounts: only the primary email transfers. Add secondary contacts manually.
7. After importing, compare the client count in JAMM PX against the row count in your TaxDome export to confirm nothing was skipped.
