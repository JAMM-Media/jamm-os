 STANDING RULES
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

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK — run before touching anything
git add -A
git commit -m "checkpoint before autopilot 3B fixes"
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.

---

# Standing verification rules — apply to every step in this task:
- Never report a file as created without running ls -la on it and including the output
- Never report a fix as working without running grep to confirm the change landed and including the output
- If any verification fails, fix it before moving to the next step
- After all steps, run: python3 -c "from app.api.concierge.route import router; print('OK')"
- Include all verification output in your final summary

---

# POST-TASK — run after task completes
find app/api/concierge/ -name "*.py" | sort
ls migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Section 3: Task to perform

Task: Rebuild JAMM Concierge autopilot — Phase 3B + 4A

Read frontend/src/components/concierge/ConciergePanel.tsx in full before writing anything. Do not remove or modify any existing functionality. Add everything below on top of what exists.

---

Step 1 — Create frontend/src/lib/events/conciergeEvents.ts

Create the file. Content:

// frontend/src/lib/events/conciergeEvents.ts

const CONCIERGE_ACTION_EVENT = 'jamm:concierge-action'

export interface ConciergeAction {
  type: 'navigate' | 'open-modal' | 'navigate-and-open'
  route?: string
  modal?: string
  prefill?: Record<string, string>
}

export function emitConciergeAction(action: ConciergeAction) {
  window.dispatchEvent(new CustomEvent(CONCIERGE_ACTION_EVENT, { detail: action }))
}

export function onConciergeAction(handler: (action: ConciergeAction) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent<ConciergeAction>).detail)
  window.addEventListener(CONCIERGE_ACTION_EVENT, listener)
  return () => window.removeEventListener(CONCIERGE_ACTION_EVENT, listener)
}

export function setFormDirty(dirty: boolean) {
  window.dispatchEvent(new CustomEvent('jamm:form-dirty', { detail: { dirty } }))
}

---

Step 2 — Add autopilot imports to ConciergePanel.tsx

Add to the existing import block at the top:

import { useRouter } from 'next/navigation'
import { emitConciergeAction } from '@/lib/events/conciergeEvents'

Add Zap to the lucide-react import line alongside X and Send.

---

Step 3 — Add autopilot state and router to ConciergePanel

Inside the ConciergePanel function, after the existing state declarations, add:

const router = useRouter()
const autopilotRef = useRef(false)
const [autopilotOn, setAutopilotOn] = useState(false)
const [statusMessage, setStatusMessage] = useState('')

Add a useEffect that syncs autopilotRef when autopilotOn changes:
useEffect(() => { autopilotRef.current = autopilotOn }, [autopilotOn])

Add a useEffect that watches statusMessage and clears it after 2000ms:
useEffect(() => {
  if (!statusMessage) return
  const t = setTimeout(() => setStatusMessage(''), 2000)
  return () => clearTimeout(t)
}, [statusMessage])

---

Step 4 — Add action detection and execution

Add this function inside ConciergePanel, before the return statement:

function handleConciergeAction(raw: string): string {
  const ACTION_MARKER = 'CONCIERGE_ACTION:'
  const actionIndex = raw.indexOf(ACTION_MARKER)
  if (actionIndex === -1) return raw

  const beforeAction = raw.slice(0, actionIndex).trim()
  const actionLine = raw.slice(actionIndex + ACTION_MARKER.length).split('\n')[0].trim()

  if (!autopilotRef.current) {
    return 'To use autopilot navigation, turn on Autopilot using the toggle above.'
  }

  try {
    const action: ConciergeAction = JSON.parse(actionLine)
    executeAction(action)
  } catch {}

  return beforeAction || ''
}

Add this function inside ConciergePanel, before the return statement:

function executeAction(action: ConciergeAction) {
  const routeToLabel: Record<string, string> = {
    '/clients': 'Navigated to Clients',
    '/settings/team': 'Navigated to Team Settings',
    '/engagements/templates': 'Navigated to Engagement Templates',
    '/settings/integrations': 'Navigated to Integrations',
    '/settings/billing': 'Navigated to Billing',
  }

  if (action.route) {
    const clientMatch = action.route.match(/^\/clients\/([^/]+)$/)
    if (clientMatch) {
      const name = decodeURIComponent(clientMatch[1]).replace(/-/g, ' ')
      const capitalized = name.replace(/\b\w/g, c => c.toUpperCase())
      setStatusMessage(`Navigated to ${capitalized}`)
    } else {
      setStatusMessage(routeToLabel[action.route] ?? `Navigated to ${action.route}`)
    }
    router.push(action.route)
  }

  if (action.modal) {
    const modalLabel: Record<string, string> = {
      'new-client': 'Opened New Client drawer',
      'new-engagement': 'Opened New Engagement drawer',
      'invite-staff': 'Opened Invite Staff modal',
      'new-template': 'Opened New Template drawer',
    }
    setTimeout(() => {
      emitConciergeAction(action)
      setStatusMessage(modalLabel[action.modal ?? ''] ?? 'Opened modal')
    }, 500)
  } else if (action.route) {
    setTimeout(() => emitConciergeAction(action), 500)
  }
}

---

Step 5 — Wire action detection into the streaming response

In the sendMessages function, find where the final streamed content is written to messages. After streaming completes, in the finally block or after the while loop ends, add a post-processing step:

After streaming is complete, read the last message content. Pass it through handleConciergeAction(content). Update the last message with the returned string.

The exact location: after the while loop and remaining buffer processing, before setStreaming(false), add:

setMessages((prev) => {
  const updated = [...prev]
  const last = updated[updated.length - 1]
  if (last.role === 'concierge') {
    updated[updated.length - 1] = {
      role: 'concierge',
      content: handleConciergeAction(last.content),
    }
  }
  return updated
})

---

Step 6 — Add autopilot toggle to the header

In the header div, between the title span and the X button, add:

<button
  onClick={() => setAutopilotOn((v) => !v)}
  title={autopilotOn ? 'Autopilot on. I\'ll navigate for you.' : 'Autopilot off'}
  className={`flex items-center gap-1 text-[11px] px-2 py-1 rounded-[4px] border border-[0.5px] transition-colors ${
    autopilotOn
      ? 'border-[#4A7FA5] bg-[#EBF4FB] text-[#4A7FA5] dark:bg-[#1a3a52] dark:text-[#7ab8d8]'
      : 'border-[#C8CDD6] bg-transparent text-[#6B7280] dark:border-[#484848]'
  }`}
>
  <Zap className="h-3 w-3" />
  Autopilot
</button>

Below that button, if autopilotOn is true, render:
<span className="text-[10px] text-[#4A7FA5] ml-1">on</span>

Wait — keep it simpler. Just render the button as above. The active state styling is sufficient.

---

Step 7 — Add status line render

In the message feed div, after the messages.map block and before the messagesEndRef div, add:

<p
  className={`text-[11px] text-[#6B7280] text-center transition-opacity duration-500 ${statusMessage ? 'opacity-100' : 'opacity-0'}`}
  style={{ minHeight: 16 }}
>
  {statusMessage}
</p>

---

Step 8 — Add resolve endpoint call for client slug

In executeAction, when a client route is detected (clientMatch), before calling router.push, call the resolve endpoint to confirm the client exists. If the resolve fails, show a status message "Could not find client" and do not navigate.

The resolve endpoint is GET /api/backend/concierge/clients/resolve?name=[decoded name].
Use the same auth header pattern already used in fetchContext.
If res.ok and data.id exists, proceed with router.push.
If not, setStatusMessage('Could not find client') and return.

Make executeAction async for this step.

---

After all steps:

1. ls -la frontend/src/lib/events/conciergeEvents.ts
2. grep -n "autopilotOn\|autopilotRef\|statusMessage" frontend/src/components/concierge/ConciergePanel.tsx
3. grep -n "emitConciergeAction\|useRouter\|Zap" frontend/src/components/concierge/ConciergePanel.tsx
4. grep -n "CONCIERGE_ACTION\|handleConciergeAction\|executeAction" frontend/src/components/concierge/ConciergePanel.tsx
5. grep -n "setTimeout\|resolve" frontend/src/components/concierge/ConciergePanel.tsx
6. python3 -c "from app.api.concierge.route import router; print('OK')"
7. npm run build from frontend directory — zero TypeScript errors
8. Browser test: autopilot OFF, send any message that would trigger navigation — panel shows nudge text, no navigation fires
9. Browser test: autopilot ON, "add a client" — navigates to /clients, New Client modal opens, status line appears and fades
10. Browser test: autopilot ON, "create an engagement for Patricia Nguyen" — navigates to her page, engagement drawer opens, status line shows her name
11. Report exact lines added in each file