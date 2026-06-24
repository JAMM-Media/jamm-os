# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# Section 3 - The task

# Task: Build 4 — Draft-and-confirm in conversation responses

USE: claude sonnet

## VERIFY BEFORE ACT

```bash
grep -n "DRAFT:\|parseDraft\|draft_block\|DRAFT_MARKER" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -10
```

Expected: no output. Draft parsing does not exist yet. If any of these strings are
present, stop and report.

```bash
grep -n "DRAFT RESPONSE PATTERNS\|draft_pattern\|propose.*confirm\|When you surface" /home/corby/jamm-os/app/api/concierge/prompts.py | head -5
```

Expected: no output. Draft instruction block does not exist yet in prompts.py.
If present, stop and report.

```bash
grep -n "def get_system_prompt" /home/corby/jamm-os/app/api/concierge/prompts.py
```

Note the line number. You will add the draft instruction block inside this function.

---

## WHAT IS BEING BUILT

When the agent calls a live data function and returns specific named clients or
engagements, it appends a short draft artifact at the end of its response.
The frontend detects the draft marker, extracts the content, renders it in the
same styled card as notification drafts, and removes it from the message bubble.

The agent only drafts when the situation is unambiguous and the action is high value.
It never drafts on general how-to questions or when no specific client or engagement
is named in the data returned.

The four draft types:
- CLIENT_EMAIL: a short professional client communication
- INVOICE_ITEMS: invoice line item suggestions
- STAFF_REASSIGN: a redistribution recommendation
- IRS_RENEWAL: a short renewal request communication

---

## ACTION — Part 1: Add draft instruction block to prompts.py

File: `/home/corby/jamm-os/app/api/concierge/prompts.py`

Inside `get_system_prompt()`, find the line that appends the autopilot block:

```python
    if autopilot_enabled:
        prompt += f"\n\n---\n\n{_AUTOPILOT_BLOCK.strip()}"
    else:
        prompt += "\n\n---\n\nAUTOPILOT MODE IS OFF..."
```

Add the following block BEFORE those two lines (before the autopilot check):

```python
    prompt += """

---

DRAFT RESPONSE PATTERNS

When you call a live data function and the result contains specific named clients
or engagements, you may append a short draft artifact at the end of your response.
Only do this when all three conditions are true:
1. You called a live data function (get_overdue_invoices, get_client_communication_gap,
   get_unbilled_completed_work, get_stalled_engagements, get_irs_auth_expiring,
   get_client_document_status, get_portal_inactive_clients).
2. The result contains at least one specific named client or engagement.
3. The natural next action is a communication or assignment, not just information.

Do NOT append a draft on general how-to questions, greetings, or when no specific
client or engagement is named.

When all three conditions are met, append the draft using this exact format at the
very end of your response, after all other content:

---DRAFT:TYPE---
[2-4 sentence draft content here]
---END DRAFT---

Replace TYPE with one of: CLIENT_EMAIL, INVOICE_ITEMS, STAFF_REASSIGN, IRS_RENEWAL

Rules for drafts:
- CLIENT_EMAIL: 2-4 sentences. Professional, warm tone. No em dashes. No filler phrases.
  Use [Client Name] as placeholder. Keep it short enough to read in 10 seconds.
- INVOICE_ITEMS: List the engagement name and suggested amount only. No prose.
- STAFF_REASSIGN: Name the engagement and the suggested staff member. One sentence.
- IRS_RENEWAL: 2-3 sentences requesting updated authorization. Use [Client Name].
  Reference the specific form type (2848 or 8821) if known.

Examples of when to draft:
- get_client_communication_gap returns 3 clients with no contact in 21 days -> CLIENT_EMAIL
- get_unbilled_completed_work returns completed work -> INVOICE_ITEMS
- get_staff_capacity shows one person overloaded with named engagements -> STAFF_REASSIGN
- get_irs_auth_expiring returns clients with expiring auths -> IRS_RENEWAL

Examples of when NOT to draft:
- User asks how to create an engagement (how-to question, no live data)
- get_daily_brief is called (summary overview, no single action implied)
- get_pipeline_bottleneck is called (diagnostic, no communication implied)
- get_staff_capacity shows normal utilization (no redistribution needed)
"""
```

---

## ACTION — Part 2: Add parseDraftFromResponse to ConciergePanel.tsx

File: `/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx`

Add this function directly above the `filterOutput` function:

```typescript
  function parseDraftFromResponse(text: string): {
    type: string
    content: string
    cleanedResponse: string
  } | null {
    const startMarker = '---DRAFT:'
    const endMarker = '---END DRAFT---'
    const startIdx = text.indexOf(startMarker)
    const endIdx = text.indexOf(endMarker)
    if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) return null

    const typeEnd = text.indexOf('---', startIdx + startMarker.length)
    if (typeEnd === -1) return null

    const type = text.slice(startIdx + startMarker.length, typeEnd).trim()
    const content = text.slice(typeEnd + 3, endIdx).trim()

    // Remove the entire draft block from the response including surrounding whitespace
    const cleanedResponse = text.slice(0, startIdx).trimEnd()

    if (!type || !content) return null
    return { type, content, cleanedResponse }
  }
```

---

## ACTION — Part 3: Wire parseDraftFromResponse into sendMessages

File: `/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx`

Add a `draft` field to the `Message` interface at the top of the file:

Find:
```typescript
interface Message {
  role: 'user' | 'concierge'
  content: string
  actionConfirm?: string
  isBriefing?: boolean
}
```

Replace with:
```typescript
interface Message {
  role: 'user' | 'concierge'
  content: string
  actionConfirm?: string
  isBriefing?: boolean
  draft?: { type: string; content: string } | null
}
```

Inside `sendMessages`, find this block:

```typescript
        const filteredAssembled = filterOutput(assembled)
        const cleanContent = handleConciergeAction(filteredAssembled)
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'concierge') {
            updated[updated.length - 1] = {
              role: 'concierge',
              content: cleanContent,
            }
          }
          return updated
        })
```

Replace with:

```typescript
        const filteredAssembled = filterOutput(assembled)
        const parsedDraft = parseDraftFromResponse(filteredAssembled)
        const textForAction = parsedDraft ? parsedDraft.cleanedResponse : filteredAssembled
        const cleanContent = handleConciergeAction(textForAction)
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'concierge') {
            updated[updated.length - 1] = {
              role: 'concierge',
              content: cleanContent,
              draft: parsedDraft ? { type: parsedDraft.type, content: parsedDraft.content } : null,
            }
          }
          return updated
        })
```

---

## ACTION — Part 4: Render draft card in message feed

File: `/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx`

Find the message rendering block. It starts with:
```typescript
          {messages.map((msg, i) => (
            <div key={i}>
            <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} items-start gap-2`}>
```

And ends with the suggestions chip block and closing `</div>`. Find the closing
`</div>` that closes `<div key={i}>` and add the draft card BEFORE the suggestions
chip block. The structure should be:

After the main message bubble div closes (the one containing the ReactMarkdown
and the isBriefing download button), add:

```typescript
              {msg.draft && (
                <div className="ml-8 mt-2 rounded-[8px] bg-[#F0F4F8] dark:bg-[#1a2a3a] border border-[0.5px] border-[#C8CDD6] dark:border-[#3a4a5a] px-3 py-2.5">
                  <p className="text-[10px] text-[#6B7280] dark:text-[#9CA3AF] mb-1.5 font-medium uppercase tracking-wide">
                    {msg.draft.type === 'CLIENT_EMAIL' ? 'Draft email' :
                     msg.draft.type === 'INVOICE_ITEMS' ? 'Draft invoice' :
                     msg.draft.type === 'STAFF_REASSIGN' ? 'Suggested reassignment' :
                     msg.draft.type === 'IRS_RENEWAL' ? 'Draft renewal request' :
                     'Draft'}
                  </p>
                  <p className="text-[12px] leading-[1.5] text-[#374151] dark:text-[#D1D5DB] whitespace-pre-wrap">
                    {msg.draft.content}
                  </p>
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(msg.draft!.content).then(() => {
                          setCopiedId(`msg-${i}`)
                          setTimeout(() => setCopiedId(null), 2000)
                        }).catch(() => {})
                      }}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[#6B7280] dark:text-[#9CA3AF] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
                    >
                      {copiedId === `msg-${i}` ? 'Copied' : 'Copy'}
                    </button>
                    <button
                      onClick={() => {
                        const confirmed = window.confirm(
                          msg.draft!.type === 'STAFF_REASSIGN'
                            ? 'Open the engagement to apply this reassignment?'
                            : msg.draft!.type === 'INVOICE_ITEMS'
                            ? 'Open billing to create this invoice?'
                            : 'Send this message to the client?'
                        )
                        if (confirmed) {
                          if (msg.draft!.type === 'STAFF_REASSIGN') {
                            router.push('/engagements')
                          } else if (msg.draft!.type === 'INVOICE_ITEMS') {
                            router.push('/billing')
                          } else {
                            handleSend(`Send this message: ${msg.draft!.content}`)
                          }
                        }
                      }}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] bg-[#1F3148] text-white hover:bg-[#2a4060] transition-colors"
                    >
                      {msg.draft.type === 'STAFF_REASSIGN' ? 'Open engagement' :
                       msg.draft.type === 'INVOICE_ITEMS' ? 'Open billing' :
                       'Send'}
                    </button>
                  </div>
                </div>
              )}
```

Place this block INSIDE the `<div key={i}>` wrapper, AFTER the main message bubble
div closes but BEFORE the suggestions chip block.

---

## VERIFY AFTER ACT

```bash
grep -n "parseDraftFromResponse\|---DRAFT:\|---END DRAFT---\|DRAFT RESPONSE PATTERNS" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -10
```

Expected: parseDraftFromResponse, ---DRAFT: marker reference, and ---END DRAFT---
all present in the file.

```bash
grep -n "DRAFT RESPONSE PATTERNS\|---DRAFT:\|---END DRAFT---" /home/corby/jamm-os/app/api/concierge/prompts.py | head -5
```

Expected: all three strings present in prompts.py.

```bash
python3 -c "
from app.api.concierge.prompts import get_system_prompt
result = get_system_prompt()
assert 'DRAFT RESPONSE PATTERNS' in result, 'FAIL: draft instruction block missing from system prompt'
assert '---DRAFT:' in result, 'FAIL: draft marker format missing'
assert '---END DRAFT---' in result, 'FAIL: end marker missing'
print('PASS: draft instruction block present in system prompt')
"
```

Expected: PASS.

```bash
cd /home/corby/jamm-os/frontend
npm run build
```

Expected: zero TypeScript errors. If errors appear, stop and report them. Do not
self-correct silently.

---

## GIT

```bash
cd /home/corby/jamm-os
git add app/api/concierge/prompts.py
git add frontend/src/components/concierge/ConciergePanel.tsx
git commit -m "build4: draft-and-confirm in conversation -- CLIENT_EMAIL, INVOICE_ITEMS, STAFF_REASSIGN, IRS_RENEWAL"
git pull --rebase origin main
git push origin main
```

If conflicts on task.md use --theirs. Conflicts on source files use --ours.