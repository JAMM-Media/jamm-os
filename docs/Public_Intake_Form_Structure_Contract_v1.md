<!-- Copied into repo 2026-08-18. Source: "JAMM PX -- Public Intake Form: Structure Contract v1.docx", sent by Andrew. -->
# JAMM PX -- Public Intake Form: Structure Contract v1

*(Structure is locked and Andrew's. Copy, context-question inventory, and visual design are Ben's. Structural changes are a conversation before they land -- standing agreement.)*

## The flow -- four steps

**Step 1 -- Broad service (routing).** Three fixed answers: Tax / Bookkeeping / Advisory. Plus a fourth: "Not sure yet" -- routes directly to contact capture, becomes a quote-path lead flagged for high owner attention. Never dismissed.

**Step 2 -- Engagement type (routing).** Shows only the firm's active engagement types in the chosen category, rendered with lead-facing labels (both served by Andrew's public config endpoint -- never hardcode the mapping). Escape answer: "None of these quite fits" -- routes back to Step 1 as an answer, not a back button.

**Step 3 -- Complexities (routing into pricing).** The resolved question set for the chosen engagement type, straight from the endpoint payload. An active-but-unconfigured type has an empty set -- skip straight to Step 4, quote path. Escape answer routes back to Step 2.

**Step 4 -- Contact capture, Turnstile, submit.** Fully priced path leads to an auto proposal. Anything unpriced, unconfigured, or not-sure leads to a quote. Quote is the universal answer; nothing a lead does dismisses them.

## Question types -- the governing distinction

- **Routing questions** change what comes next. They are exactly the ones named above. Adding, removing, or reordering one is a structural change, meaning a conversation with Andrew first.

- **Context questions** change nothing downstream. They exist so the owner walks into the call informed. Any step may carry them.

- **Conditional follow-ups**: a context question may unfold deeper questions based on its answer. Follow-ups never route. The moment a context question changes the flow, it's a routing question in disguise and belongs in the map via conversation.

## The brainstorm -- Ben's dedicated session, and it's bigger than it sounds

This is not "write some copy." This is mapping the full context-question web for the entire top of the funnel, and done right it will sprawl before it tightens. The shape to hold onto: the four routing steps are a straight spine; the context web hangs off the spine and never becomes it. A lead always travels broad service -> engagement type -> complexities -> capture. The web decorates that line with intel-gathering; it never redirects it.

What the session has to produce, per routing answer:

- **The full candidate inventory first, pruned second.** For every answer at Steps 1 and 2, brainstorm everything a firm owner would want to know before the call with that kind of lead. Chose Tax -> business or individual? Filed last year? Self-prepared or prior accountant, and why the switch? Chose Bookkeeping -> up to date? What software? Who does it now? Chose Advisory -> what triggered looking for help? Revenue band? These are illustrative, not the list -- the session generates the exhaustive version, then cuts it down under the friction discipline. Generate wide, ship narrow.

- **The conditional depth for each survivor.** Each kept question gets its follow-up tree sketched explicitly: which answers unfold deeper questions, how deep it goes (two levels should be rare, three suspect), and where each branch terminates. Every branch of every follow-up rejoins the spine at the same next routing step, drawn out, not assumed.

- **The opt-out wording per question.** Every context question carries its explicit out ("not sure" / "rather discuss on the call"). Wording is Ben's; existence is not negotiable.

- **The summary-card rendering.** For each question, decide how its answer (including declines and backtracks) reads on the owner's pre-call card. A question whose answer can't earn a useful line on that card probably shouldn't survive the cut -- that's the test for whether it justifies its friction.

- **The written artifact.** The output is a document Andrew can read: the spine, the web hung off it, every branch terminated. If drawing it reveals pressure to change the spine itself, a new routing question, a reorder, that's the standing agreement: conversation first, before anything lands.

## Universal answer rules

- Every question, routing or context, carries an explicit out. Routing outs navigate backward; context outs record and proceed. No silent skips, no browser-style back button; every exit is an answer.

- Every answer, backtrack, and final choice writes a durable event row (existing intake event seam). The behavioral log may mirror them; owner-facing surfaces read the durable rows. Recorder, never gatekeeper.

- Partial saves persist throughout (existing warm-path spec).

## Owner payoff (Ben's lead detail + summary card)

The journey renders as pre-call intel: first answers, backtracks, final landing, context answers, declines. Example shape: "Advisory -- business -- ~12 employees -- initially considered bookkeeping -- declined to say how far behind on books."

## Friction discipline

Context questions cost conversion. Keep them few and optional-feeling; the event rows will show exactly which question leads abandon on, so tune against real data, not instinct.
