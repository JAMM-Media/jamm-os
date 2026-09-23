# Firm Library — Ready for Launch

Build reference for finishing the Firm Library feature. Everything below is
already decided and drafted. Nothing here is speculative — this is what to
build against.

---

## 1. Architecture decision

**Two separate sections, not one shared list.**

### Starter Templates (new)
- Read-only, `vendor_sample` items only
- General acknowledgment gates first entry to this section
- The only action available on an item here is **"Create a draft from
  this"** — copies the item into the firm's real Firm Library as a new
  `firm_draft` row
- The two engagement letter skeletons get the extra visible notice (see
  Section 3 below) since they're structural frameworks, not finished
  content

### Firm Library (existing, unchanged in concept)
- Only ever contains a firm's own `firm_draft` and `firm_approved` items
  — never raw vendor samples sitting alongside real work
- Publishing a draft derived from either engagement letter skeleton
  triggers the second, letter-specific acknowledgment before it can go
  `firm_approved`
- Everything else works exactly as the existing
  `document_template_status_service.py` already supports

**Why two sections, not one:** the acknowledgment only makes sense as a
real gate if there's a real boundary to gate. A shared list has no natural
moment to interrupt someone; a separate section does. This also matches
Canopy's real, documented pattern (per research) — firms copy a starter
into their own space and it becomes genuinely theirs, edited with their
own language, while the source stays untouched and separate.

---

## 2. Backend status

Built and pushed to `main` tonight:

- `app/core/enums.py` — `TemplateStatus(str, Enum)`: `vendor_sample`,
  `firm_draft`, `firm_approved`
- `app/models/document_template_status.py` — polymorphic
  `item_type`/`item_id` (document or folder, no DB-level FK), one row per
  real item, `published_by`/`published_at` preserved as audit history
  across a `revert_to_draft`
- `app/services/document_template_status_service.py` — `get_status`,
  `set_draft`, `publish`, `revert_to_draft`. Gated to `firm_owner`,
  `manager`, or `system_admin` only (no engagement-administrator concept
  applies at firm scope)
- 5 guard tests, all watched red then green, including tenant isolation

**Known, deliberate gap — real follow-up task, not forgotten:**

`source_item_id` does not exist yet. This surfaced *after* the schema task
was written, once the liability research made clear why it matters: a
firm's draft or approved copy needs to know which vendor original it came
from, so that if JAMM ever updates a starter template later, a firm's
already-customized or already-approved version is never silently
overwritten. This needs its own small, additive migration (one nullable
column) before the "Create a draft from this" flow is built, since that
flow is what actually needs to write the value.

---

## 3. Disclaimer and acknowledgment copy (final, ready to use)

### Template detail page / editor notice

Visible on every Starter Templates item's detail page and inside the
editor. For the two engagement letter skeletons specifically, this must be
impossible to miss before someone starts editing.

> **Starter template — professional review required**
>
> This template is provided for general informational and
> workflow-convenience purposes. It is not legal, tax, accounting, or
> other professional advice, and it is not tailored to your firm, your
> services, your clients, or your jurisdiction. JAMM PX does not
> represent or warrant that this template is complete, current,
> compliant, enforceable, or appropriate for any particular use.
>
> Your firm is solely responsible for reviewing, customizing, and
> approving the final document, and should obtain advice from qualified
> legal counsel before using it with a client.

### Acknowledgment — general (required once, first time a firm opens Starter Templates)

> I understand that these are editable starter templates, not legal or
> professional advice. My firm is responsible for reviewing, customizing,
> and approving any document before it's used with a client.
>
> ☐ I understand and agree

### Acknowledgment — engagement letters specifically (required before publishing a draft derived from either engagement letter skeleton)

> This document is a starter framework with placeholder legal language.
> Before publishing this for use with clients, I confirm my firm has
> reviewed and completed the legal sections, and had this document
> reviewed by qualified counsel or our professional liability insurer as
> appropriate.
>
> ☐ I confirm this has been reviewed

**Note:** actual Terms of Service language covering JAMM's own legal
exposure was deliberately *not* drafted here — that needs a real lawyer,
not a chat draft. This document only covers the two pieces that are safe
to finalize as plain product copy: the visible notice and the
click-through acknowledgments above.

---

## 4. Style guide used for all six documents

Applied consistently, not per-document guesswork:

**Voice, as tensions**
- Direct, not stiff — say the thing plainly, don't dress it up
- Warm, not chatty — no forced friendliness or exclamation points
- Confident, not authoritative-sounding — write like someone who's done
  this before, not a policy document performing expertise
- Short sentences allowed to just end
- Specific over general

**Anti-pattern blacklist**

| Don't write | Write instead |
|---|---|
| "This ensures a seamless and efficient onboarding experience." | "This gets your client set up correctly the first time." |
| "It's important to note that deadlines are firm." | "Deadlines are firm." |
| "We are committed to providing exceptional service." | (cut entirely) |
| "Please don't hesitate to reach out with any questions." | "Questions? Ask your firm contact." |
| "This document serves as a comprehensive guide to..." | "This explains how to..." |
| "In order to complete this process..." | "To do this..." |

**Override rule:** if a sentence would sound strange said out loud to a
real client sitting across a desk, rewrite it.

---

## 5. The six full documents (complete drafts)

### 5.1 Staff Guide — How Templates Work in JAMM PX

**What a template actually is**

JAMM PX ships your Firm Library with a handful of starter documents
already sitting in it, labeled **Sample**. Think of them as a head start,
not a finished product. You'd never send a Sample to a client as-is. It's
there so nobody on your team has to start from a blank page.

**The three states**

Every template lives in one of three states:

- **Sample** — what JAMM shipped. Nobody can edit it directly.
- **Draft** — your firm's own working copy. Only a firm owner or manager
  can create or touch one.
- **Approved** — done, published, ready to use. Any staff member can use
  it. Only an owner or manager can change it, replace it, or send it back
  to Draft.

**Turning a Sample into something you'll actually use**

1. Open the Sample in Firm Library.
2. Click "Create a draft from this." Your firm gets its own copy to edit.
   The original Sample stays put, so you can always start over if the
   edit goes sideways.
3. Rewrite it for your firm: real fees, real terms, your state, your
   process. Cut whatever doesn't apply.
4. When it's ready, a firm owner or manager clicks "Approve." Now your
   whole team can use it.

**A couple of things worth knowing**

Only one Draft and one Approved copy of each template exists per firm, so
you're never hunting through versions. If you approve something and later
need to fix it, pull it back to Draft, edit, re-approve. Your firm still
keeps the record of who approved it and when, even after you pull it
back.

Staff can use an Approved template, but they can't edit it. If something's
wrong with it, that's an owner or manager conversation.

**If your firm uses AI to help draft or edit anything from this library**

That's fine, plenty of firms do. A few things worth building into how you
use it:

- A real person reviews anything AI touched before it goes to a client.
  Not a skim, an actual read.
- Whoever signs or sends the document is responsible for it, the same as
  if they'd written every word themselves. "AI wrote it" isn't a defense
  if something's wrong.
- If AI was used on something a client will see, especially an engagement
  letter, say so. Most firms handle this with a line in the engagement
  letter itself.
- Don't take AI-generated numbers, tax positions, or citations at face
  value. Check them against a real source before they go anywhere.

None of this is unique to JAMM PX, it's the same standard most
professional bodies already expect from firms using AI tools generally.
It just applies here too.

**One important note on the engagement letters**

The two engagement letter templates aren't finished contracts. They're
structure only, section headings and prompts telling you what belongs
where, not the actual legal wording. That's deliberate. Engagement
letters are contracts, and the right wording depends on your state, your
services, and how much risk your firm is willing to carry. Before you
approve either one, get it in front of your attorney or your professional
liability insurer. JAMM PX gives you the skeleton. Your firm supplies the
legal language.

---

### 5.2 New Client Intake Form

*For office use: route to the appropriate service checklist after this
form is complete. This form does not create an engagement. No work begins
until a signed engagement letter is on file.*

**1. What brings you in**

- Type: Individual / Sole proprietor / Business entity / Trust or estate
  / Other
- Services you're looking for: 1040 / Business return / Bookkeeping /
  Payroll / Sales tax / Advisory / Notice or letter from the IRS or state
  / Catch-up or cleanup / Other
- **Tell us what's going on, in your own words:**

  *(a few lines of open space)*

- Any hard deadlines we should know about (a filing date, a notice
  response date, a loan closing, etc.)
- How did you hear about us?

**2. Your information** *(individuals)*

- Legal name, preferred name, date of birth
- Address, phone, email
- Occupation
- State(s) you lived or worked in this year
- Spouse's information, if filing jointly
- Dependents: name, relationship, date of birth, months lived with you
- Have you filed before? With us or elsewhere? Do you have your
  prior-year return?
- Have you had any identity theft issues or an IP PIN from the IRS?

**3. Your business** *(if applicable)*

- Legal name, DBA if different, EIN
- Entity type (sole prop, partnership, S-corp, C-corp, other)
- Date and state of formation
- What the business does, and roughly how big it is (revenue, employees)
- Owners and their ownership percentage
- Any related businesses we should know about

**4. Where things stand today**

- What software do you currently use for bookkeeping?
- When was the last time your books were reconciled?
- List your bank, credit card, and loan accounts — institution name and
  last four digits only. Please don't send account numbers or online
  banking passwords through this form.
- Do you currently have a bookkeeper or accountant? Are they aware you're
  looking elsewhere?

**5. Anything open or unresolved**

- Any unfiled returns, in any year?
- Any letters or notices from the IRS or a state agency, open or recently
  resolved?
- Any payment plans, liens, or audits — past or current?
- Anything else going on that we should know before we start?

**6. What you're looking for from us**

- What would make this a success for you?
- How often would you like to hear from us?
- Who's the main point of contact on your end?

**Before you submit**

By submitting this form, you're confirming the information above is
accurate to the best of your knowledge, and giving us permission to
contact you about it. This form is for gathering information only — it
doesn't mean we've agreed to take you on as a client, and no work begins
until you've signed an engagement letter with us.

---

**Internal use only — not shown to the prospective client**

- Conflict check completed: Y / N
- Reason client is leaving prior firm (if known):
- Records available: prior returns / financials / trial balance /
  notices / formation documents
- Deadline feasible given current records: Y / N
- Any risk flags (aggressive positions, cash-heavy business, repeated
  preparer changes, unresolved notices, refusal to provide records)?
- Decision: Accept / Accept with conditions / Decline
- Approved by: _______________ Date: _______________

---

### 5.3 New Client Onboarding Checklist

This starts once the engagement letter is signed, not before. Nothing on
this list means "do the work" — it means "get the client properly set up
so the work can happen correctly."

**1. Engagement activation**

- Signed engagement letter on file
- Correct legal client name(s) and entity confirmed
- Retainer or first payment received, if required
- Client created in our practice management system, billing system, and
  document system — check for duplicates first

**2. Team setup**

- Engagement owner, preparer, and reviewer assigned
- Correct workflow template applied, with real deadlines, not
  placeholders
- Client folder created

**3. Client access**

- Client invited to the portal
- Confirm they can actually log in — don't just confirm the invite was
  sent
- Explain how we communicate and how to upload documents
- Any required consent forms sent and signed (privacy notice,
  information-sharing consent, etc.)

**4. Getting their records**

- Document request sent, with a real due date
- Prior-year returns or financials received, if applicable
- If switching from another firm: their contact info requested, and
  anything unresolved from the transition noted below
- Opening balances confirmed for bookkeeping clients — bank accounts,
  loans, AR/AP, payroll liabilities

*Missing items log:*

| Item | Requested | Due | Received | Notes |
|---|---|---|---|---|
| | | | | |

**5. Kickoff**

- Kickoff call or meeting held with the client's main contact
- Scope reconfirmed out loud — what's included, what's not, how often
  they'll hear from us
- Client knows who approves what on their end
- Recurring due dates from the client (documents, approvals, etc.)
  explained
- Any open questions written down here, with an owner and a date:

  *(space for notes)*

**6. First real deliverable**

- First cycle of work completed using our normal review process, not a
  shortcut
- Opening numbers reconciled to source records, if bookkeeping
- Reviewed and approved internally before it goes to the client
- Delivered to the client through the portal, with a short explanation of
  what they're looking at
- Client confirmed they received it and reviewed it

---

**Onboarding isn't done until the first deliverable has actually gone out
and been reviewed — not when the setup tasks above are checked off.**

Completed by: _______________ Date: _______________

*If your firm requires a second person to confirm onboarding is complete
before billing begins, add a reviewer line here.*

---

### 5.4 Individual Tax Organizer

*Tax year: __________ Client name: __________*

Fill this out as completely as you can. If something doesn't apply, leave
it blank or mark N/A rather than guessing. Where we ask you to upload a
document, attach it through the portal rather than mailing or emailing
it.

**Before you start**

- Please return this by: __________
- If we didn't prepare your return last year, please attach a copy of
  your most recent federal and state returns.
- Mark each item Yes, No, or N/A. If you're not sure, mark it and add a
  note — don't skip it.

**1. Your information**

- Name, date of birth, occupation
- Address, phone, email
- Marital status as of December 31. If it changed this year (marriage,
  divorce, separation, death), tell us the date.
- Spouse's name, date of birth, occupation (if filing jointly)
- Did you or your spouse have an identity theft issue or an IP PIN from
  the IRS this year? Y / N

**2. Dependents and household**

For each dependent: name, relationship, date of birth, months lived with
you, and whether anyone else might also claim them.

| Name | Relationship | DOB | Months in home | Student/disabled? |
|---|---|---|---|---|
| | | | | |

**3. What changed this year**

Check anything that applies, and give us a sentence on each:

- Marriage, divorce, or death in the family
- Bought, sold, or refinanced a home
- Had a baby, adopted, or gained a new dependent
- Started, closed, or changed a business
- Job loss, retirement, or new job
- Moved to a different state
- Bought, sold, or received digital assets (crypto, NFTs, etc.)
- Received a letter or notice from the IRS or a state agency
- Foreign income, foreign accounts, or foreign inheritance
- Anything else worth mentioning:

**4. Income**

Attach the actual forms where you have them. This list is here so
nothing gets missed.

- Wages (W-2)
- Interest and dividends (1099-INT, 1099-DIV)
- Investment sales (1099-B) — including crypto
- Retirement and Social Security (1099-R, SSA-1099)
- State refund, unemployment, gambling winnings, or other 1099s
- Rental income, by property
- K-1s from any partnership, S-corp, estate, or trust
- Self-employment or gig income (1099-NEC, 1099-K, or cash not on a form)
- Anything else you were paid this year that isn't listed above:

**5. Adjustments and deductions**

- HSA contributions
- Retirement contributions (IRA, SEP, etc.)
- Student loan interest
- Medical expenses
- Property taxes, mortgage interest
- Charitable donations — cash and non-cash. For non-cash over $500,
  please attach a receipt or appraisal.

**6. Credits**

- Childcare provider name, address, and amount paid
- Education: school name, tuition paid, 1098-T if you have it
- Health insurance through the marketplace (1095-A)
- Energy-efficient home improvements or an electric vehicle purchase

**7. Payments already made**

- Estimated tax payments — dates and amounts
- Any overpayment from last year applied to this year

**The next two sections only apply if they're relevant to you.** If you
don't own a business or rental property, skip ahead to the signature line
at the end.

**8. If you have a business** *(Schedule C)*

Attach a separate copy of this section for each business.

- Business name, what it does, when it started (if this year)
- Total income received
- Expenses by category (we'll walk through this with you if it's your
  first year)
- Vehicle use — business miles vs. total miles
- Any assets purchased this year (equipment, vehicles, etc.)
- Do you have employees or contractors? Have 1099s been issued to
  contractors?

**9. Rental property** *(if applicable)*

- Address, dates you owned/rented it this year
- Rental income received
- Expenses — mortgage interest, insurance, repairs, management fees
- Any improvements made this year

---

**Before you send this back**

- Anything missing that you're still waiting on:
- Questions for us:
- I confirm this information is complete and accurate to the best of my
  knowledge.

Signature: _______________ Date: _______________

---

### 5.5 Month-End Close Checklist

*Client: __________ Period: __________ Basis: Cash / Accrual*

This checklist assumes standard bookkeeping. Skip anything that doesn't
apply to this client, and mark it N/A rather than leaving it blank.

**1. Before you start**

- Confirm all bank, credit card, and other statements for the period
  have been received
- Confirm the prior period's close is fully done — no open items carried
  forward without a note
- Confirm any recurring entries or templates are ready to use

**2. Get everything recorded**

- All bank and credit card transactions categorized through period end
- Any cash, checks, or transfers not on a bank feed recorded manually
- All customer invoices and vendor bills entered for the period
- Payroll for the period posted, including taxes and benefits

**3. Reconcile**

- Each bank account reconciled to the statement, zero unexplained
  difference
- Each credit card reconciled
- Accounts receivable tied to the general ledger — review aging, flag
  anything stale
- Accounts payable tied to the general ledger — review aging
- Payroll liabilities reconciled to the payroll provider's report
- Loans reconciled to the lender statement
- Sales tax reconciled, if applicable

*(Accrual basis only — add if this client's books are accrual:)*

- Prepaid expenses and deferred revenue adjusted for the period
- Accrued expenses and accrued revenue recorded
- Depreciation and amortization posted
- Inventory or work-in-progress adjusted, if applicable

**4. Review the numbers**

- Trial balance reviewed for anything unusual — negative balances,
  dormant accounts, duplicates
- Every material balance sheet account has a real reconciliation behind
  it — nothing sitting in "uncategorized" or "ask my accountant"
- P&L compared to last month and last year — anything more than [set a
  real threshold] different gets a note explaining why
- Financial statements match the final trial balance

**5. Handle exceptions**

- Anything unresolved logged here, with who owns it and when it needs to
  be fixed:

| Item | Amount | Owner | Due | Resolved? |
|---|---|---|---|---|

- A second person reviews the reconciliations and the financials before
  anything goes out — not the same person who did the work, if your firm
  has more than one person

**6. Close it out**

- Final report package generated (balance sheet, P&L, and anything else
  this client gets)
- Notes added for any real variance or open item
- Delivered to the client
- Period locked so nothing changes after delivery without a real reason
  and a note

---

Completed by: _______________ Date: _______________
Reviewed by: _______________ Date: _______________

---

### 5.6 Firm Letterhead / Correspondence Master

This is a shell for any letter going out under the firm's name, not a
specific piece of correspondence. Replace every bracketed item with your
firm's real information before using it.

---

**[FIRM LOGO]**

**[Firm's exact legal or registered name]**
[Street address, City, State ZIP]
[Phone] · [Email] · [Website]

---

[Date]

[Recipient name]
[Recipient title, if applicable]
[Recipient address]

**Re: [Subject of this letter]**

Dear [Recipient name],

[Body of the letter goes here.]

[Closing paragraph — next steps, what you need from them, or how to
reach you with questions.]

Sincerely,

[Signer's name]
[Signer's title / credentials]
[Direct phone or email, if different from the firm's general line]

---

**[Firm's registered address, if different from above]**
[Phone] · [Website] · [Secure client portal link]

*[State-required disclosure, license number, or "not a CPA firm"
statement, if applicable in your state — check with your state board.]*

---

A few notes on using this, not part of the letter itself:

- Keep the header and footer locked once your firm sets them, don't let
  individual staff redesign the letterhead each time they write to a
  client.
- The credential shown after a signer's name (CPA, EA, etc.) should
  always match what that person is actually licensed to use. Check your
  state's rules before adding "CPA," "CPA firm," or similar language to
  the header, some states restrict this based on ownership and staff
  composition.
- If a letter is more than one page, make sure page 2 onward still
  identifies the firm and the client, in case pages get separated.
- Don't put anything sensitive, a Social Security number, a full account
  number, in the subject line or anywhere in the footer.

---

## 6. The two engagement letter skeletons

### 6.1 Form 1040 Engagement Letter — Starter Framework

*This is a structural outline, not a finished letter. Every bracketed
prompt needs your firm's own language, reviewed by your attorney or
professional liability insurer before this is used with a real client.
JAMM PX provides the structure. Your firm provides the legal language.*

---

**[Firm letterhead]**

[Date]

[Client name(s) — use separate letters for spouses, adult children, or
related entities you don't intend to jointly represent]

**Re: Engagement to Prepare [Tax Year] Individual Income Tax Return**

**Parties and purpose**
*State who this letter is between, and that its purpose is preparing the
named return(s). Name the client exactly as they'll appear on the
return.*

**Scope — what's included**
*List the exact federal form and schedules, and every state/local return
by name. Don't write "all required returns." State whether extension
preparation is included. State whether your firm will e-file, and what
authorization you need from the client to do that.*

**Scope — what's not included**
*Name what this engagement does not cover: other states, other years,
amended returns, tax planning, notice response, audit representation,
bookkeeping, entity returns, anything else the client might assume is
included but isn't. [Consult counsel: some firms use a standard
exclusions list across all individual engagements — decide if yours
should.]*

**Our responsibilities**
*Describe how you'll prepare the return: from client-provided
information, using professional judgment on positions taken, making
inquiries when something looks off. [Consult counsel: reference your
applicable professional standards — AICPA SSTS, Circular 230, or your
state's rules, whichever actually apply to your credential.]*

**Client responsibilities**
*State what the client owes you: complete and accurate information, all
relevant documents, prompt answers to follow-up questions, final review
of the completed return before it's filed, responsibility for paying tax
and estimates on time.*

**No assurance**
*State plainly that this isn't an audit of the client's information, and
that you're not verifying what they give you beyond reasonable inquiry.*

**When this engagement ends**
*State when you consider the engagement complete — typically after
delivery and filing of the named return(s), or after delivery for client
self-filing. [Consult counsel: be specific here, this is one of the most
commonly under-specified sections.]*

**Fees**
*State your fee basis and what triggers additional charges — extra
forms, disorganized records, additional states, rush work. [Consult
counsel or your own pricing policy for the actual numbers and terms.]*

**Confidentiality and data**
*Describe how client information is protected, what systems/portal you
use, and your record retention period.*

**[If applicable] Section 7216 consent**
*If tax return information will be used or disclosed for anything beyond
preparing the return itself, this needs a separate, properly worded
consent — not buried in this letter. [This section requires counsel
review; the IRS prescribes specific content for valid 7216 consent.]*

**Legal terms**
*[Consult counsel for: termination rights, governing law, dispute
resolution, any limitation of liability language. These vary
significantly by state and by what your insurer will actually
support — do not copy generic versions of these clauses from another
firm or template.]*

**Acceptance**

Signature: _______________ Date: _______________
[Client name]

---

### 6.2 Monthly Bookkeeping Engagement Letter — Starter Framework

*Same rule as above: structure only, no finished legal language. Have
this reviewed before real use.*

---

**[Firm letterhead]**

[Date]

[Client legal entity name]

**Re: Recurring Bookkeeping Services Engagement**

**Parties, objective, and term**
*Name the client entity and firm, the objective of the recurring
service, the start date, and the term (ongoing, with what notice period
to end it). [Consult counsel on renewal/termination language.]*

**Services included**
*List exactly what you'll do and how often — don't use "including but
not limited to." For each service (transaction categorization,
reconciliations, AR/AP, payroll-related tasks, sales tax, close,
reporting), state what's included, the frequency, and what you need from
the client to do it.*

**Services not included**
*Name what this doesn't cover — audit, review, or compilation of
financial statements, tax return preparation, tax planning, payroll
processing (if you don't do it), bill payment or check-signing
authority, legal or valuation advice. [Consult counsel: if you're
preparing financial statements as part of this engagement, this section
needs to address AR-C 70 requirements — ask your counsel or reviewer
whether that applies to your service.]*

**Our responsibilities**
*Describe what you'll do: perform the listed services at the stated
cadence, using information the client provides, and communicate
anything that doesn't reconcile or looks wrong.*

**Client responsibilities**
*State what the client owes: a designated person to oversee the
engagement and approve entries/classifications, timely and complete
source documents by an agreed cutoff, review of what you deliver, and
responsibility for their own records, internal controls, and business
decisions. [This section matters for independence reasons if this
client is also an attest client — flag that to counsel if it applies.]*

**Authority and access**
*State clearly what you can and can't do without separate approval — can
you initiate payments, submit payroll, file returns? Who has to approve
what? List authorized contacts on the client's side.*

**Cutoffs and turnaround**
*State the client's monthly document deadline and your target
close/delivery timing, worded as dependent on receiving complete
information by that deadline, not as an unconditional promise.*

**Fees**
*State the recurring fee, billing date, what's included in that fee, and
what triggers a price change (more accounts, more transaction volume,
new entities). [Consult counsel or your pricing policy for actual terms,
including what happens on late payment.]*

**Ending the engagement**
*State the notice period to end this, what happens to open work and
access at that point, and the client's responsibility to find a
successor and track their own deadlines after transition.*

**Legal terms**
*[Consult counsel for: confidentiality, data handling, dispute
resolution, governing law, any liability limitation. As with the 1040
letter, don't copy these from elsewhere without your own review.]*

**Acceptance**

Signature: _______________ Date: _______________
[Client name / authorized signer]

---

## 7. What's left to build

1. **`source_item_id` migration** — small, additive, one nullable column
   on `document_template_status`. Needed before the "Create a draft from
   this" flow, since that flow writes the value.
2. **Convert the six documents + two skeletons into real files** — likely
   `.docx`, matching this codebase's other document types.
3. **Seeding mechanism** — creates the 8 items as real `Document` rows,
   `vendor_sample` status, in every new firm's Starter Templates section.
   Decide: part of firm creation, or a separate onboarding step.
4. **Starter Templates section (frontend)** — new UI area, read-only
   list, general acknowledgment gate on first entry, "Create a draft from
   this" action.
5. **Firm Library publish/draft UI (frontend)** — status badges, the
   Draft → Approve → (optional) revert-to-draft flow, the
   engagement-letter-specific acknowledgment before publish.
6. **Real Terms of Service language** — not drafted here. Needs a real
   lawyer. Everything else in this document is ready to build against
   without waiting on that.
