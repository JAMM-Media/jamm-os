# JAMM PX Perfect Assistant Build

## What This Document Is

This is the north star for the JAMM Concierge. Not a task list, not a sprint plan, not a list of bugs to fix this week. This is the description of what the agent looks like when it is finished, when it is perfect, when there is nothing left to add. We are allowed to set this higher than what is currently possible. That is the point. We are not writing down what we can build by Friday. We are writing down what a firm owner should be able to expect from an assistant that actually deserves the word Concierge, and then we spend the rest of this project's life closing the distance between where we are and what is written here.

This document does not get diluted to match reality. Reality gets pulled up to match this document. When something here feels unreachable, that is correct. Leave it. Chase it.

Every real gap found in live use gets checked against this document. If it is already described here, we found where the product fell short of the standard, and we fix it. If it is not described here yet, we add it, because the standard was incomplete, not because the bug was acceptable.

---

## The Vision

Picture the firm owner who has never touched JAMM before today. They do not read documentation. They do not click through a settings menu looking for a toggle. They do not memorize where anything lives. They open the Concierge panel and they talk to it the way they would talk to the most competent, most present, most obsessively on-top-of-everything operations person they have ever worked with, someone who has been embedded in their firm since day one, who has read every engagement, memorized every client, tracked every dollar, watched every deadline, and never once needed to be reminded of anything.

They ask it anything. It already knows. Not because it went and checked, though it may have, silently, in the background, before answering. It knows the way a person who has been paying full attention for months knows. There is no moment where the firm owner thinks "I probably know more about my own firm than this thing does." That sentence should be structurally impossible to say about JAMM Concierge. If it is ever said, something is broken, and we go find out what.

The agent is not a search bar with a friendly voice. It is not a FAQ that happens to stream its answers in word by word. It is the single most informed presence in the entire firm, at every moment, about everything that firm does.

That is the bar. Everything below is what reaching that bar actually requires, described in as much detail as we can manage, so nothing gets missed and nothing gets quietly excused as good enough.

---

## The Core Standard

The agent must know the real, current, live answer to any factual question about the firm's own data. No exceptions carved out for domains that are hard to build tools for. No exceptions carved out for questions that are awkward to classify. If the data exists anywhere inside JAMM, in any table, behind any feature, touched by any workflow, the agent can retrieve it and answer with it, immediately, in the same breath the question was asked. Telling a firm owner to go look at a page themselves is not a lesser answer. It is a failure. It means the thing we built to replace that exact action did not do its job.

We are not asking for the agent to be well informed. We are asking for it to be maximally, exhaustively, unreasonably informed, to the point where "how would it not know this" becomes the only reasonable reaction to any gap we find.

### The one honest exception: clarification is not ignorance

This has to stay precise or the standard collapses the first time someone tests it.

**Ignorance is never acceptable.** The agent does not know something that already exists in the firm's data right now. The invoice is overdue. The record exists. The agent said it didn't know. That is always, unconditionally, a bug, and it goes on this document as a gap the moment it is found.

**Legitimate clarification is not the same failure.** If a firm owner asks the agent to take an action and the one missing detail is something that lives only inside the firm owner's head, something no amount of internal knowledge could have produced, the agent asking is not a failure, it is the same thing a sharp, competent employee would do. "Draft an email about the overdue invoice" when six different clients currently have one is not a knowledge gap. It is an honest need for one more word.

But this exception has exactly one rule protecting it from being used as an excuse: the agent must have already checked everything it could check on its own before asking. If there was only one overdue invoice and it still asked which client, that is not clarification. That is the first failure wearing the second one's clothes. Every clarifying question the agent asks should survive the test: could it have figured this out itself first. If yes, and it didn't try, it's a bug.

---

## Section 1: Total Knowledge Coverage

The standard for every single domain below is identical and non negotiable: the agent can answer any specific, real, live question about the firm's actual current data in that domain, in full detail, on the spot, the first time it is asked, without ever needing to be told to check again or look somewhere else.

### Clients
Every client's status, health, contact details, entity type, the date they were added, which staff member is assigned to them, their portal login status, and the ability to find any client from a partial name, a nickname, or a rough description. If a firm owner says "that construction client from last spring," the agent should be able to work with that the way a person who actually remembers the client would.

### Engagements
Every engagement's status, deadline, assigned staff, associated client, whether it is stalled or moving normally, its type (1040, 1120, 1120S, 1065, 990, amended, or anything else the firm uses), whether it came from a recurring template, and its full history. Nothing about the shape or state of a single engagement should ever require the firm owner to go look.

### Tasks and checklist items
Every task's status, who it is assigned to, its deadline, which engagement it belongs to, and a running, always current answer to "what is overdue" at the task level, not just the engagement level.

### Document requests
Every outstanding request, exactly which client has not uploaded what, which items were waived and why, and the live completion state of every checklist tied to every engagement.

### Client portal
Who has logged in, who has not, how long it has been, the state of every portal invite and every magic link, and a real answer to "who is actually using this" at any moment, not a vague impression.

### Billing and invoicing
Every overdue invoice with client, amount, and exact days overdue, every piece of unbilled completed work sitting unconverted, every payment and partial payment, and the true, current total accounts receivable for the whole firm at any second it is asked.

### Time tracking
Every logged hour, by staff member, by engagement, billable against non billable, and every hour of completed work that has not yet become an invoice.

### Automations
Which automations are live, which have actually fired recently, and which ones are silently not firing when they should be, before the firm owner ever has to notice the silence themselves.

### IRS authorizations
Every 2848 and 8821, which are expiring, which have expired, which client each belongs to, and the real renewal status of each one.

### Calendar and deadlines
Every upcoming deadline across the whole firm, sliceable by staff member or by client, and full awareness of the firm's actual working calendar including holidays.

### Staff
Every staff member's current capacity, workload, role, assigned engagements, credentials, and CPE record status, answered with the same confidence as if the agent had just walked the floor and asked everyone directly.

### QC checklists
The live completion status of every quality control checklist tied to every engagement, and exactly what is still outstanding on each one.

### Notes
Real awareness of note content where it is relevant to a question being asked, even if a dedicated tool is not warranted for every single note in isolation.

### Firm chat
Full understanding of how firm chat works as a feature, even where message level privacy means it should not surface actual conversation content.

### Settings and firm configuration
Branding, integrations, notification preferences, subscription status, and every other configuration detail a firm owner might reasonably ask about.

### Signature envelopes
Sent, pending, signed, and the real resend or cancel status of every envelope, tied to its actual location in the product rather than a description of where someone assumed it lived.

### Current tool inventory, to be verified and expanded as this grows

`get_daily_brief`, `get_stalled_engagements`, `get_unbilled_completed_work`, `get_overdue_invoices`, `get_staff_capacity`, `get_client_communication_gap`, `get_pipeline_bottleneck`, `get_client_full_snapshot`, `get_weekly_summary`, `get_deadline_calendar`, `get_automation_health`, `get_portal_inactive_clients`, `get_irs_auth_expiring`, `get_client_document_status`.

Visible gaps against everything described above: no dedicated tool yet for tasks and checklist items independent of engagement level status, none for QC checklist completion specifically, none for time tracking detail beyond unbilled work, none for signature envelope status. Confirm each of these live before assuming it is missing. Every confirmed gap becomes its own scoped task, never a single giant rebuild, per how we already work.

---

## Section 2: Interaction Quality

Knowing everything means nothing if the way it is delivered feels clumsy, robotic, mistimed, or wrong. This section is the standard for how the knowledge actually reaches the firm owner.

- Every operational question that a registered tool could answer actually reaches that tool. The keyword classifier is a living thing, not a list written once and left alone. Every time a real phrasing slips through uncaught, that phrasing gets added.
- No response ever tells a firm owner to go look something up manually when a tool exists that could have answered it directly. This is the single most important line in this entire document. Read it twice.
- Suggestion chips are always genuinely relevant to the response just given, never a leftover from the previous topic, never generic filler.
- Suggestion chips never appear before the message they belong to has finished revealing itself. The chip is a footnote to the answer, not a competitor to it.
- Draft responses never carry a suggestion chip underneath them. The draft's own action button is the only next step that should exist in that moment.
- Every draft reflects real, current data at the exact moment it is generated. Never stale. Never assumed.
- Response latency sits inside a range that feels instant to a person who is busy running a firm, not a range that is merely acceptable on a benchmark chart.
- Terminology is always exactly right. Engagement, never project. Staff, never employees. Firm, never company. Practice Experience, never practice management. Andrew, never Andy.
- No em dashes, anywhere, ever.
- Bold used consistently for UI terms. Lists used consistently for steps. The formatting itself should feel considered, not accidental.
- The agent never fabricates a number, a name, or a status to fill a silence. A failed tool call surfaces as a diagnosable, logged event, never as a friendly sounding wrong answer standing in for the truth.

---

## Section 3: Security and Safety, Confirmed Standing

- The guard classifier reliably blocks unsafe requests before they ever reach the main model.
- SSN and EIN patterns are redacted from every output without exception.
- Attempts to leak the system prompt are caught and blocked every time.
- Prompt injection patterns in user messages are detected reliably.
- Firm level lockout after repeated violations functions exactly as designed.
- Every real question logs to ConciergeQuestionLog with an accurate low_confidence flag, every single time, with no silent failures.

---

## Section 4: Open Decisions Standing Between Us and This Standard

These are not tasks. They are decisions that have to be made before the related tasks can even be written.

- What is the maximum acceptable response time for a standard question, and is the current model and effort level actually meeting it.
- When a single draft touches multiple clients at once, what does sending it actually do.
- What does a real, minimal review surface for ConciergeQuestionLog's low_confidence entries look like, and who is responsible for watching it.

---

## Section 5: The Launch Gate

Before August 15, 2026, every domain in Section 1 and every standard in Section 2 gets walked, tested live, and either confirmed true or logged here as an explicit, owned exception. Nothing gets left unchecked silently. Nothing gets assumed fine because nobody looked.

- Item:
- Reason deferred:
- Owner:
- Target date:

---

## How We Actually Use This

Every real gap found in live use, starting with the overdue invoices failure that prompted this document, gets root caused fully first, then checked against everything written here. If it is already described, we found exactly where the build fell short of the standard we already set, and we go fix it. If this document did not describe it yet, the standard itself was incomplete, and we expand this document before we write the task.

This document is never finished being aimed at. It is allowed to describe things that feel out of reach today. That is not a flaw in the document. That is the entire reason it exists.
