<!-- Converted from "JAMM PX CRM Build Contract, Addendum 1.docx", copied into repo 2026-08-14 -->

JAMM PX CRM Build Contract, Addendum 1
The Fee Schedule Foundation, Form Projection, and Send Safety
August 12, 2026. Author: Andrew. Supplements the CRM Build Contract sent August 12, 2026. Where the contract or the nurture preset tree is ambiguous or disagrees with this document, this document governs.
# 1. The system in one page: read this first
A design session on August 12 resolved everything fuzzy between a booked call and a signed letter, and in doing so restructured the foundation your build sits on. The core idea:
The intake form is a projection of firm configuration. Firms never edit the form; they configure their firm, and the form renders itself.
Firms configure two things. A service catalog: which of the 43 canonical engagement types they offer, each activated with a pricing mode and a template. A fee schedule: for each offered service, a base fee plus complexity pricing built from system-defined questions where the firm only ever attaches numbers and prices, never writes lead-facing text. Your form reads a public config endpoint (Andrew's track) and renders exactly what that firm offers and asks. One firm's form asks about crypto in five volume tiers; another never mentions crypto. Nobody built two forms, and no service or question list is ever hardcoded on the frontend.
The automation prices proposals from the same configuration, sends them from the firm's templates, and stops for a human at every point where judgment enters: after calls, on every typed reply, and whenever a lead's answers land outside what the firm consciously priced. The rest of this document specifies those mechanics.
# 2. The service catalog and what your form shows
•       There are 43 canonical engagement types (Appendix A). The enum is expanding from 17 as part of Andrew's next build; consume the canonical values from the backend, verbatim, with display labels as pure presentation. Never hand-copy the list: the existing letter templates settings tab has a hand-copied list already out of sync (other_advisory missing), and that same drift on the intake form silently loses leads.
•       The form shows only the services the firm has activated, plus an Other option. A catalog entry is the single source of truth for offered: activation binds the pricing mode and the automation-default template together, so a service cannot be half-on and your form, the engine, and the Concierge all read one state.
•       The Other path: lead record created, automation stops, firm owner notified that a lead wants something off-menu. The system never tells a lead no; it hands the conversation to a human.
•       Every firm starts with all 43 templates present but dormant and nothing activated. Choosing offered services is an onboarding step (see section 8).
# 3. Complexity questions: how the form asks them
Complexity is captured as structured facts, two layers deep at most: a flag question first (did you sell crypto or digital assets this year), then follow-ups that exist only because the firm priced that dimension. The system defines all flags, dimensions, and vocabularies; firms attach prices. Three dimension kinds reach your form:
•       Boolean: yes or no, no follow-up.
•       Categorical: system-written options (e.g. exchange trading, staking, mining, DeFi, NFTs), plus an Other option on every categorical question. The firm prices the options it covers.
•       Numeric: the form asks the natural question generated from the firm's chosen unit (roughly how many transactions, or roughly what total dollar amount) and captures the raw number. The server maps it to the firm's tier; the form never sees tiers, prices, or boundaries.
•       A categorical answer can open one numeric sub-question (type, then volume within that type). Never deeper than two. Additional numeric questions for the same flag are flat siblings, and some are purely informational: asked to arm the firm owner for the call, no price effect.
•       Submission payload is facts only: flag keys, canonical option IDs, raw numbers. No free text except the Other fields.
# 4. Pricing, quotes, and the universal quote law
•       Fee resolution is backend and arrives with Andrew's fee schedule build: base fee plus the answered adders. Your build never computes fees client-side.
•       Three pricing modes per service: fixed (full automation); starting at (proposal says starting at, final pricing confirmed on scoping); quote required (no number: the intake routes to the firm owner to price, the automation resumes on their one click).
•       The universal quote law: any lead answer landing on anything without a price attached routes to needs-a-quote. That covers: numbers above the firm's highest priced range, the Other option on any question, categorical options the firm did not price, and guard thresholds (a firm can set a threshold on any dimension, e.g. total proceeds over 1M dollars, that overrides everything and forces a quote). One law, enforced in the engine at one point. Nothing silently fails and nothing gets mispriced.
•       Merge-field validation before any automated external send: the renderer leaves unresolved {{tags}} literally in the output, so the send path must validate every field resolves (validate_context exists for this) and on any missing field: do not send, notify the firm owner with the specific fields, hold for review. A raw {{fee_amount}} must never reach a lead.
# 5. The post-call gate
The engine cannot know whether a lead joined a call and is forbidden to judge how it went. When the scheduled time passes, the sequence holds and the firm owner is prompted with exactly three answers, zero typing:
•       Went well, continue: the sequence advances toward the proposal.
•       Not a fit right now: the lead moves to the long-term drip.
•       No-show: the reschedule branch fires. A no-show is a scheduling failure, not a rejection, and must not be dripped as one.
The button press is the fact the engine consumes. No timer, no inferred attendance, no calendar signal may substitute for it.
# 6. Proposal accept: the click path and the typed path
•       The click path. The proposal email carries an Accept answer button. A click is an unambiguous machine-readable fact. A firm-level setting governs it: auto-send enabled, the engagement letter sends immediately and the firm owner is notified it went out; disabled, the accept is recorded and the firm owner gets a one-click confirmation before the letter sends.
•       The setting defaults to require approval. Firms opt into auto-send once they trust the machine. The Concierge mentions this toggle during onboarding so firms wanting the full-speed path find it on day one.
•       The typed path. Anything the lead types, including yes I accept in words, is a reply, and replies always pause (section 7). The toggle has no effect on typed responses. Only the button click can ride the automated path.
# 7. Inbound replies
•       Any inbound reply pauses the sequence and notifies the firm owner. No exceptions. Reply content is judgment, not fact; the engine never parses, classifies, or branches on it.
•       The notification offers two one-click options: continue the automation (advances exactly as if the pause had not happened), or stop automation, custom response needed (halts that lead until the firm owner re-engages manually).
•       No inbound response of any kind ever auto-fires the next phase. The CRM takes the busy work, not the judgment calls. That is the design.
# 8. The Concierge onboarding checklist
The system's honesty now depends on firm configuration, so onboarding is load-bearing and the Concierge (your lane) drives a completeness checklist rather than a tour:
•       Services activated in the catalog (an empty catalog means a form advertising nothing).
•       Pricing complete for every activated service: mode chosen, base fee set, complexity dimensions priced or consciously left to quote.
•       Templates reviewed: accepted as-is, customized, or replaced with an uploaded PDF (a static document with no merge fields; the firm accepts that trade-off by choosing it).
•       The accept toggle decided, with the default-approval framing explained.
•       Merge fields confirmed resolvable, especially {{fee_amount}} vs hard-written pricing in the template body.
•       And beyond onboarding: flag untouched things. A crypto question live for 30 days with no tiers priced, an activated service with no base fee. Unconfigured surface area is a standing Concierge signal, not a one-time check.
# 9. What Andrew's track delivers, in order
•       Build 1, fee schedule (first): the enum expansion to 43, the service catalog model, the fee schedule tables, backend fee resolution, and the public config endpoint your form consumes. Endpoint contract: per firm, active types with display labels, complexity questions with system-written text, categorical options with opaque IDs, numeric questions per the firm's unit. Never prices, adders, guards, or the schedule itself.
•       Build 2, templates: one guaranteed template per engagement type in every firm (present by migration and creation hook); exactly one automation-default per type per firm, database-enforced; immutable versioning with every sent letter and proposal stamped with the producing version; uploaded PDFs as a supported kind. Your lookup is: engagement type in, template out. No fallback logic on your side.
•       Template copy is being authored deliberately in a separate content session (these letters are liability documents); placeholder bodies may exist before ratified copy arrives as new versions ahead of your proposal phase.
Step zero remains unchanged: confirm the v2 ML spec read. This document does not alter your phase order; it makes the intake form and proposal phases concrete before you reach them, and the form phase should consume the config endpoint rather than anything hardcoded.
# Appendix A: the 43 canonical engagement types
Individual tax: 1040; 1040-NR nonresident; 1040-X amended; 4868 extension.
Business and entity tax: 1120; 1120-S; 1065; 990 nonprofit; 1041 trust and estate; 706 estate; 709 gift; amended business return; 7004 extension; 8868 extension.
Payroll and information reporting: 941 quarterly; 940 annual FUTA; payroll processing (recurring); 1099 and W-2 preparation.
Sales tax: sales and use tax filing. Foreign reporting: FBAR and international information returns.
Bookkeeping and accounting: monthly; quarterly; cleanup and catch-up; accounting system setup and migration.
Financial statements: compilation; review; audit; agreed-upon procedures.
Advisory and representation: tax planning advisory; fractional CFO; entity formation and new business setup; IRS notice resolution; tax resolution; audit representation.
Specialty: R&D tax credit study; nonprofit formation and exemption (1023/1024); employee benefit plan filing (5500); business valuation; business personal property tax; cost segregation study; transaction advisory (sell-side due diligence and quality of earnings).
Catch paths: other advisory; custom; plus the form's Other button.
Multi-state and state-only filings are complexity flags on the federal engagement type, not separate types. Cost segregation, business valuation, and transaction advisory default to quote required in v1.
