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

Task: Add autopilot to ConciergePanel.tsx

Read frontend/src/components/concierge/ConciergePanel.tsx in full before writing anything. Do not remove or modify any existing code. Only add what is specified below.

---

STEP 1 — Add imports

Find the existing import block at the top of the file. Add these two lines after the existing imports:

import { useRouter } from 'next/navigation'
import { Zap } from 'lucide-react'
import { emitConciergeAction, type ConciergeAction } from '@/lib/events/conciergeEvents'

Verification — print lines 1 to 15 of the file:
sed -n '1,15p' frontend/src/components/concierge/ConciergePanel.tsx

Do not proceed to Step 2 until this output shows all three new imports.

---

STEP 2 — Add state and router

Find the line: const hasInitialized = useRef(false)

Add these lines immediately after it:

const router = useRouter()
const autopilotRef = useRef(false)
const [autopilotOn, setAutopilotOn] = useState(false)
const [statusMessage, setStatusMessage] = useState('')

Then add these two useEffects after the existing useEffects:

useEffect(() => { autopilotRef.current = autopilotOn }, [autopilotOn])

useEffect(() => {
  if (!statusMessage) return
  const t = setTimeout(() => setStatusMessage(''), 2000)
  return () => clearTimeout(t)
}, [statusMessage])

Verification — print the section containing hasInitialized and the new state:
grep -n "hasInitialized\|autopilotRef\|autopilotOn\|statusMessage\|useRouter" frontend/src/components/concierge/ConciergePanel.tsx

Do not proceed to Step 3 until all five variables appear in the output.

---

STEP 3 — Add handleConciergeAction and executeAction functions

Add these two functions inside the ConciergePanel component, immediately before the return statement.

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

async function executeAction(action: ConciergeAction) {
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
      const capitalized = name.replace(/\b\w/g, (c) => c.toUpperCase())
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

Verification — print the last 80 lines of the file:
tail -80 frontend/src/components/concierge/ConciergePanel.tsx

Do not proceed to Step 4 until handleConciergeAction and executeAction are visible in the output.

---

STEP 4 — Add autopilot toggle to header and status line to message feed, wire action detection into streaming

4a — Find the header div containing the JAMM Concierge title span and the X close button. Add this button between the title span and the X button:

<button
  onClick={() => setAutopilotOn((v) => !v)}
  title={autopilotOn ? "Autopilot on. I'll navigate for you." : 'Autopilot off'}
  className={`flex items-center gap-1 text-[11px] px-2 py-1 rounded-[4px] border border-[0.5px] transition-colors ${
    autopilotOn
      ? 'border-[#4A7FA5] bg-[#EBF4FB] text-[#4A7FA5] dark:bg-[#1a3a52] dark:text-[#7ab8d8]'
      : 'border-[#C8CDD6] bg-transparent text-[#6B7280] dark:border-[#484848]'
  }`}
>
  <Zap className="h-3 w-3" />
  Autopilot
</button>

4b — Find the line: <div ref={messagesEndRef} />
Add this immediately before it:

<p
  className={`text-[11px] text-[#6B7280] text-center transition-opacity duration-500 ${statusMessage ? 'opacity-100' : 'opacity-0'}`}
  style={{ minHeight: 16 }}
>
  {statusMessage}
</p>

4c — Find the sendMessages function. After the streaming while loop completes and before setStreaming(false), add:

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

Verification — run all four of these and include every line of output:
1. grep -n "Autopilot\|autopilotOn\|Zap" frontend/src/components/concierge/ConciergePanel.tsx
2. grep -n "statusMessage\|minHeight" frontend/src/components/concierge/ConciergePanel.tsx
3. grep -n "handleConciergeAction" frontend/src/components/concierge/ConciergePanel.tsx
4. npm run build from frontend directory — zero TypeScript errors

Do not report success unless all four verifications pass and the build is clean.

---

Final verification — browser tests:
1. Open the app. Confirm the Autopilot button appears in the Concierge panel header next to the X button.
2. Autopilot OFF, type "add a client" — confirm nudge text appears, no navigation fires.
3. Autopilot ON, type "add a client" — confirm navigation to /clients, New Client modal opens, status line appears and fades.
4. Report exactly what happened in each browser test including any errors in the console.