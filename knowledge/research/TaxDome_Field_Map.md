# TaxDome Field Map
## For JAMM Concierge Phase 4 Source Intelligence

---

## Accounts CSV Export -- Column Reference

TaxDome exports accounts with one row per account. Multiple contacts attached to the same account appear as additional columns on the same row (Linked contact #1, Linked contact #2, etc.), not as separate rows.

| TaxDome Column | Data Type | Example Value | JAMM PX Field | Notes |
|---|---|---|---|---|
| Account Name | Text | Smith Family | client.name | Required. Blank rows skipped on import. |
| Account Type | Text | Individual | client.entity_type | Values: Individual, Business, Trust, Estate. Non-profit maps to non_profit. Unknown values: entity_type not set, warning logged. |
| Email | Text | george@email.com | client.email | Primary contact email. May be blank. |
| Phone | Text | 555-123-4567 | client.phone | May be blank. |
| Tags | Text | VIP, 1040 | client.tags | Comma-separated. JAMM PX stores as-is. |
| State | Text | CA | client.state | Two-letter state code. May be blank. |
| Linked contact #1 | Text | George Smith | Not directly mapped | Contact name only. No email in this column. Import contacts CSV separately for full contact data. |
| Linked contact #2 | Text | Nancy Smith | Not directly mapped | Same as above. Scales with max contacts per account. |
| Assigned team members | Text | Jane Doe | Not mapped on import | Staff assignments must be set manually after import. |
| Last login date | Date | 2024-03-15 | Not imported | Read-only history data. Not migrated. |
| Account creation date | Date | 2023-01-10 | Not imported | Not migrated. JAMM PX sets its own created_at on import. |
| Custom CRM fields | Various | Varies | Not mapped | Custom field values export as columns but JAMM PX has no equivalent custom field system at import. Flag for manual review. |

**Columns JAMM PX does not import from TaxDome Accounts export:**
- Assigned team members (set manually after import)
- Last login date
- Account creation/update dates
- Number of active jobs/tasks/proposals
- Timezone
- Account roles
- Custom CRM field definitions (values export but definitions do not)
- Linked contact detail beyond name

**JAMM PX client fields with no TaxDome equivalent (manual entry required after import):**
- entity_subtype
- company_name
- address_line1, address_line2, city, postal_code, country
- notes
- portal access (must be enabled and magic-link sent manually)
- IRS authorization records (see IRS section below)

---

## Contacts CSV Export -- Column Reference

TaxDome exports contacts with one row per contact. This is a separate export from Accounts.

| TaxDome Column | Data Type | Example Value | JAMM PX Field | Notes |
|---|---|---|---|---|
| First Name | Text | George | Parsed from client.name | JAMM PX stores full name not split. Concatenate First + Last. |
| Last Name | Text | Smith | Parsed from client.name | See above. |
| Email | Text | george@email.com | client.email | Primary email. |
| Phone | Text | 555-123-4567 | client.phone | |
| Company | Text | Smith LLC | client.company_name | |
| Street Address | Text | 123 Main St | client.address_line1 | |
| City | Text | San Diego | client.city | |
| State/Province | Text | CA | client.state | |
| Country | Text | US | client.country | |
| Zip | Text | 92101 | client.postal_code | |
| Notes | Text | Long-term client | client.notes | |
| Tags | Text | VIP | client.tags | |

**Import convention mismatch (critical):**
TaxDome Accounts export = one row per account, contacts as columns.
TaxDome Contacts export = one row per contact.
JAMM PX import = one row per contact, with Account Name to link.

Firms cannot re-import the Accounts CSV directly. They must use the Contacts CSV or manually restructure the Accounts CSV before importing into JAMM PX.

---

## Jobs CSV Export -- Column Reference

| TaxDome Column | Data Type | Example Value | JAMM PX Field | Notes |
|---|---|---|---|---|
| Job Name | Text | 2024 1040 Smith Family | engagement.name | Required. Blank rows skipped. |
| Client | Text | Smith Family | engagement.client_id | Matched by name against existing JAMM PX clients. Import clients before jobs. |
| Pipeline | Text | 1040 Tax Return | Not mapped | JAMM PX has no pipeline concept. Engagement type is set separately. |
| Stage | Text | Prepare Return | Not mapped | TaxDome stages do not map 1:1 to JAMM PX statuses. See stage mapping table below. |
| Status | Text | Active | engagement.status | Mapped via status map. See below. |
| Due Date | Date | 2024-04-15 | engagement.filing_deadline | Parsed in multiple formats: YYYY-MM-DD, MM/DD/YYYY, MM-DD-YYYY, DD/MM/YYYY. |
| Description | Text | Federal 1040 return | engagement.notes | Stored as internal note on import. |
| Assignees | Text | Jane Doe | Not mapped on import | Staff assignments must be set manually. |
| Priority | Text | High | Not mapped | JAMM PX has no priority field on engagements. |
| Start Date | Date | 2024-01-15 | Not mapped | JAMM PX uses due/filing dates, not a start date field. |
| Internal deadline | Date | 2024-04-01 | Not mapped | No equivalent. |
| Completion date | Date | 2024-04-10 | Not mapped | JAMM PX sets completed_at when status changes to completed. |
| Comments | Text | Client slow to respond | Not mapped | Flattened text, not structured. Not imported. |
| Linked documents | Text | doc_id_123 | Not mapped | Document links not importable via CSV. |
| Linked invoices | Text | inv_456 | Not mapped | Invoice links not importable via CSV. |

**Columns JAMM PX does not import from TaxDome Jobs export:**
- Pipeline name
- Stage name (use status mapping instead)
- Assignees (set manually)
- Priority
- Start date
- Internal deadline
- Comments
- Linked documents
- Linked invoices
- Stage history (only current stage exports -- full history is lost)

**JAMM PX engagement fields with no TaxDome equivalent:**
- engagement_type (must be set manually or inferred from job name)
- extended_deadline
- assigned_staff (set manually)
- engagement templates (not transferred)

---

## TaxDome Status and Stage Mapping

### Job Status Mapping

| TaxDome Job Status | JAMM PX Engagement Status |
|---|---|
| Active | active |
| Completed | completed |
| Archived | archived |
| On hold | draft |
| Waiting for Client | active |
| Waiting for Signatures | in_review |
| Extended | active |

### Pipeline Stage Name Mapping (common examples)

| TaxDome Stage Name | JAMM PX Equivalent Status |
|---|---|
| Lead / Intake | draft |
| Organizer Sent / Questionnaire Sent | draft |
| Docs Requested / Waiting for Docs | draft |
| Review Docs / Collect Documents | active |
| Prepare Engagement Letter | active |
| Prepare Return / Bookkeeping / Cleanup | active |
| Review / Internal Review / Partner Review | in_review |
| Ready to File / Signatures Pending | in_review |
| E-file / File Return | in_review |
| Deliver to Client | completed |
| Billing / Invoice / Collect Payment | completed |
| Post-Filing / Year-End Wrap-Up | completed |
| (Archived in any stage) | archived |

Note: TaxDome stage names are entirely custom per firm. These are common examples only. The Concierge should ask the firm owner what their specific stage names mean before mapping.

---

## IRS Authorization Data

TaxDome does NOT export IRS authorization records (Form 8821 or Form 2848) as structured data.

What TaxDome stores: Authorization forms exist as PDFs in client document folders. The IRS transcript connection is a boolean per client (connected or not). There are no structured fields for CAF number, tax years authorized, authorization type, or effective dates.

What this means for JAMM PX migration:
- No automated transfer is possible.
- Firms must manually review each client's document folder in TaxDome, locate the 8821 or 2848 PDF, and manually create an IRS authorization record in JAMM PX for each client.
- The IRS Authorization Expiry Warning automation preset in JAMM PX requires an active authorization record to fire. These records must be created manually for all migrating clients.
- Recommended approach: batch by client type. Tax clients first. Enter tax years, form type, and valid until date from the PDF.

---

## Multi-Contact Handling

TaxDome supports multiple contacts per account. A single account (e.g., a married couple filing jointly) can have multiple contacts, each with their own email address and portal login.

Export behavior: Accounts CSV puts all contacts as additional columns on one row (Linked contact #1, Linked contact #2). Contact detail (email, phone) is in the separate Contacts CSV with one row per contact.

Import behavior: JAMM PX creates one client record per imported row. For multi-contact accounts, the firm must decide whether to:
1. Create one JAMM PX client record per account (one email address, primary contact only), or
2. Create separate JAMM PX client records for each contact and link engagements manually.

JAMM PX does not natively support multiple portal logins per client record. If a married couple both need portal access, the recommended approach is to use the primary contact's email for portal access and note the secondary contact in the client record's notes field.

---

## TaxDome Portal vs JAMM PX Portal Feature Comparison

| Feature | TaxDome | JAMM PX |
|---|---|---|
| Document upload | Included | Included |
| Document download | Included | Included |
| E-signature | Included, unlimited | Included |
| Invoices and online payment | Included (CPACharge removed Jan 2026, now Stripe-based) | Included (Stripe) |
| Secure messaging / chat | Included | Included (Messages tab) |
| Organizers / questionnaires | Included | Included (Tax Organizer tab) |
| Tasks / to-dos for client | Included (Waiting for Action) | Included (To-do tab) |
| Mobile app (iOS / Android) | Included, dedicated app | Included, PWA (add to home screen) |
| Custom portal domain | Add-on (extra cost) | Included |
| Custom branding / logo | Basic included, advanced add-on | Included |
| Multiple contacts per account | Included | Single contact per client record |
| Bulk organizer export | Per-organizer only, no bulk | Not applicable |
| Client chat history export | Not exportable | All messages stored in JAMM PX |
| IRS transcript connection | Included | Not in JAMM PX (external to platform) |

Key difference to communicate to migrating firms: TaxDome's client portal requires the client to download a dedicated mobile app. JAMM PX's portal is a PWA -- clients add it to their home screen from Safari or Chrome without downloading anything from an app store.
